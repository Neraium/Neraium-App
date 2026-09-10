"""Source-clock transport and opt-in full representative WWTP workflow."""
from copy import deepcopy
from datetime import datetime, timedelta
import io
import csv
import json
import math
import os
import subprocess

import pytest

from backend.workbench import authority, intake
from test_workflow import client, IDENTITY
from test_paired import full_result


def representative_csv(comparison=False):
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(['timestamp', 'flow [L/s]', 'pressure [bar]', 'power [kW]'])
    start = datetime(2026, 6 if comparison else 1, 1)
    for i in range(8640):
        degraded = comparison and i >= 4320
        wave = math.sin(i / 4)
        writer.writerow([(start + timedelta(minutes=15*i)).strftime('%Y-%m-%d %H:%M:%S'),
                         80 + 4*wave, 55 + 2*math.cos(i*2) if degraded else 40 + 2*wave,
                         28 + wave if degraded else 20 + wave])
    return stream.getvalue().encode()


def mapping():
    return dict(pair_confirmed=True, context="", signals=[dict(column=f'{name} [{unit}]', meaning=name,
                unit=unit, include=True, reason='') for name, unit in [('flow', 'L/s'), ('pressure', 'bar'), ('power', 'kW')]])


def test_exact_source_clock_intake_and_pair():
    tables = [intake.parse(representative_csv(c), 'representative.csv') for c in (False, True)]
    originals = deepcopy(tables)
    validations = [intake.auto_validate(t, allow_source_clock=True) for t in tables]
    assert all(v['eligible_timestamps'] and v['row_count'] == 8640 and v['timestamp_mode'] == intake.SOURCE_CLOCK_MODE for v in validations)
    payload = intake.paired_input(*tables, *validations, mapping())
    for table, dataset in zip(tables, [payload['reference'], payload]):
        assert [r['timestamp'] for r in dataset['rows']] == [r['timestamp'] for r in table['rows']]
        assert not any('UTC' in t for t in dataset['transformations'])
    assert tables == originals
    with pytest.raises(intake.TimestampReview):
        intake.auto_validate(tables[0])  # Single-period support remains unchanged.
    aware = deepcopy(tables[1])
    for row in aware['rows']: row['timestamp'] += 'Z'
    with pytest.raises(ValueError, match='timestamp modes must match'):
        intake.paired_input(tables[0], aware, validations[0], intake.auto_validate(aware), mapping())


@pytest.mark.parametrize('bad', ['2026-01-01', '2026-01-01T00:15:00', '2026-01-01 00:15:00.000',
    '2026-02-30 00:15:00', '2026-1-01 00:15:00', ' 2026-01-01 00:15:00', '2026-01-01 00:15:00Z', '1700000000'])
def test_malformed_or_mixed_source_clock_requires_review(bad):
    table = intake.parse(f'timestamp,flow\n2026-01-01 00:00:00,1\n{bad},2\n'.encode(), 'x.csv')
    with pytest.raises(intake.TimestampReview):
        intake.auto_validate(table, allow_source_clock=True)


@pytest.mark.parametrize('last', ['2026-01-01 00:00:00', '2025-12-31 23:45:00'])
def test_source_clock_duplicates_and_order_block(last):
    table = intake.parse(f'timestamp,flow\n2026-01-01 00:00:00,1\n{last},2\n'.encode(), 'x.csv')
    assert not intake.auto_validate(table, allow_source_clock=True)['eligible_timestamps']


@pytest.mark.parametrize('bad', [None, 'timezone', 'source', 'governed', 'mode', 'version'])
def test_source_clock_response_boundary(monkeypatch, bad):
    monkeypatch.setattr(authority, 'identity', lambda: IDENTITY)
    monkeypatch.setenv('NERAIUM_AUTHORITY_ROOT', '/unused')
    payload = dict(mode='paired', rows=[{'timestamp': '2026-01-01 00:00:00'}], reference={'rows': [{'timestamp': '2025-01-01 00:00:00'}]})
    supplied = dict(contract_version='supplied-reference-v1.1', timestamp_mode=intake.SOURCE_CLOCK_MODE,
                    timestamp_format='%Y-%m-%d %H:%M:%S', timing_basis='direct_source_clock_datetime_differences',
                    source_timezone={'status': 'timezone_not_supplied', 'value': None},
                    reference={'source_timestamps': ['2025-01-01 00:00:00']}, comparison={'source_timestamps': ['2026-01-01 00:00:00']})
    if bad == 'timezone': supplied['source_timezone']['value'] = 'UTC'
    if bad == 'source': supplied['comparison']['source_timestamps'][0] += 'Z'
    if bad == 'mode': supplied['timestamp_mode'] = 'timezone_aware'
    if bad == 'version': supplied['contract_version'] = 'unsupported'
    result = {**full_result(), 'supplied_reference': supplied}
    result['analysis_result']['sii_evidence']['supplied_reference'] = {} if bad == 'governed' else supplied
    response = dict(contract=authority.CONTRACT, operation='analyze', catalog={}, runtime={}, result=result)
    monkeypatch.setattr(subprocess, 'run', lambda *a, **kw: subprocess.CompletedProcess([], 0, json.dumps(response), ''))
    if bad:
        with pytest.raises(authority.AuthorityError): authority.call(payload)
    else:
        assert authority.call(payload)['result'] == result


@pytest.mark.skipif(not os.getenv('NERAIUM_TEST_AUTHORITY_ROOT'), reason='Opt-in full pinned authority run')
def test_full_8640_source_clock_workflow(client, monkeypatch):
    monkeypatch.setenv('NERAIUM_AUTHORITY_ROOT', os.environ['NERAIUM_TEST_AUTHORITY_ROOT'])
    monkeypatch.setenv('NERAIUM_AUTHORITY_COMMIT', authority.SUPPORTED_COMMIT)
    existing = client.post('/api/evaluations', json={'label': 'Existing record'}).json()
    before = client.get('/api/evaluations/' + existing['id']).content
    eid = client.post('/api/evaluations', json={'mode': 'paired'}).json()['id']
    url = '/api/evaluations/' + eid
    sources = []
    for comparison, role in [(False, 'reference'), (True, 'comparison')]:
        raw = representative_csv(comparison)
        uploaded = client.post(url + f'/source?filename=representative-{role}.csv&role={role}', content=raw)
        assert uploaded.status_code == 201, uploaded.text
        sources.append((uploaded.json()['source_id'], raw))
        validated = client.post(url + f'/validate?role={role}', json={})
        assert validated.status_code == 200, validated.text
        assert validated.json()['eligible_timestamps'] and validated.json()['row_count'] == 8640
    preview = client.post(url + '/mapping-preview', json=mapping())
    assert preview.status_code == 200, preview.text
    assert client.post(url + '/approve-mapping', json={'preview_id': preview.json()['id'], 'confirmed': True}).status_code == 200
    executed = client.post(url + '/runs')
    assert executed.status_code == 201, executed.text
    run = client.get('/api/runs/' + executed.json()['id']).json()
    assert run['status'] in {'complete', 'limited'}, run.get('error')
    assert run['response']['identity']['commit'] == authority.SUPPORTED_COMMIT
    result = run['response']['result']
    assert result['processing_trace']['modules_failed'] == []
    supplied = result['supplied_reference']
    assert supplied['timestamp_mode'] == 'naive_historical_source_clock'
    assert supplied['source_timezone'] == {'status': 'timezone_not_supplied', 'value': None}
    assert result['analysis_result']['sii_evidence']['supplied_reference'] == supplied
    for role, dataset in [('reference', run['input']['reference']), ('comparison', run['input'])]:
        assert len(dataset['rows']) == supplied[role]['row_count'] == 8640
        assert supplied[role]['source_timestamps'] == [r['timestamp'] for r in dataset['rows']]
    onset = result['temporal_analysis']['lead_time_estimate']
    assert onset['timing_basis'] == 'direct_source_clock_datetime_differences'
    assert onset['timestamp'] is not None
    assert onset['seconds_since_comparison_start'] == (datetime.fromisoformat(onset['timestamp']) - datetime.fromisoformat(run['input']['rows'][0]['timestamp'])).total_seconds()
    persistence = result['persistence_analysis']['adaptive_persistence']
    assert persistence['rows_used'] == 8640 and persistence['elapsed_time_available']
    assert persistence['timestamp_profile']['median_interval_seconds'] == 900
    assert persistence['observed_duration_seconds'] == 8640 * 900
    runner = result['compatibility']['sii_runner_result']
    assert runner['timestamp_basis'] == 'source_clock_seconds_since_comparison_start'
    assert runner['latest_state']['timestamp'] == 8639 * 900
    assert run['evidence_sections']
    review = client.post(f"/api/runs/{run['id']}/reviews", json={'reviewer': 'Local representative verification', 'evidence_reviewed': True})
    assert review.status_code == 201, review.text
    report_url = f"/api/reviews/{review.json()['id']}/report"
    exported = client.get(report_url)
    assert exported.status_code == 200
    assert 'timezone_not_supplied' in exported.text and 'naive_historical_source_clock' in exported.text
    assert authority.SUPPORTED_COMMIT in exported.text
    for sid, raw in sources: assert client.get(f'/api/sources/{sid}/original').content == raw
    assert client.get('/api/evaluations/' + existing['id']).content == before
    assert client.get(report_url).content == exported.content
