"""Counter policy/provenance checks; authority classifications are explicit fixtures."""
from copy import deepcopy
import json
import hashlib
from pathlib import Path

import pytest

from backend.workbench import api, authority
from backend.workbench.mapping import exclude_unsupported_counters, EXCLUSION_REASON
from test_workflow import client, IDENTITY
from test_paired import full_result

UNITS = json.loads((Path(__file__).parents[2] / 'frontend/src/wwtp.test-fixture.json').read_text())


def wwtp_pair(client):
    eid = client.post('/api/evaluations', json={'mode': 'paired'}).json()['id']
    url = '/api/evaluations/' + eid
    sources = []
    for month, role in enumerate(('reference', 'comparison'), 1):
        raw = ('timestamp,' + ','.join(UNITS) + '\n' + '\n'.join(
            f'2026-0{month}-01 00:{i * 15:02d}:00,' + ','.join(str(j + i) for j in range(18))
            for i in range(3))).encode()
        source = client.post(url + f'/source?filename={role}.csv&role={role}', content=raw).json()
        sources.append((source['source_id'], raw))
        assert client.post(url + f'/validate?role={role}', json={}).status_code == 200
    mapping = {'pair_confirmed': True, 'signals': [dict(column=c, meaning=c, unit=u, include=True, reason='') for c, u in UNITS.items()]}
    return url, mapping, sources


def catalog(payload):
    return {role: {s['meaning']: {'telemetry_category': 'cumulative_counter' if s['column'] == 'energy_total_kwh' else 'equipment_process',
                                 'source_column': s['column']}
                   for s in payload['signals']} for role in ('reference', 'comparison')}


def test_wwtp_exclusion_workflow_and_immutable_evidence(client, monkeypatch):
    existing = client.post('/api/evaluations', json={'label': 'Existing record'}).json()
    existing_url = '/api/evaluations/' + existing['id']
    before = client.get(existing_url).content
    calls = []
    monkeypatch.setattr(authority, 'identity', lambda: IDENTITY)
    def call(payload, operation='analyze'):
        calls.append((operation, deepcopy(payload)))
        return {'identity': IDENTITY, 'catalog': catalog(payload), **({'result': full_result()} if operation == 'analyze' else {})}
    monkeypatch.setattr(authority, 'call', call)
    url, mapping, sources = wwtp_pair(client)
    preview = client.post(url + '/mapping-preview', json=mapping)
    assert preview.status_code == 200, preview.text
    preview = preview.json()
    assert [len(p['signals']) for _, p in calls] == [18, 17]
    assert calls[0][1]['rows'][0]['energy_total_kwh'] == 13
    assert 'energy_total_kwh' not in calls[1][1]['rows'][0]
    assert preview['input_sha256'] == api.digest(calls[1][1])
    excluded = preview['mapping']['signals'][13]
    assert excluded == {**mapping['signals'][13], 'include': False, 'reason': EXCLUSION_REASON}
    record = preview['exclusions'][0]
    assert record['classification'] == 'cumulative_counter'
    assert record['classification_input_sha256'] == api.digest(calls[0][1])
    assert record['identity'] == IDENTITY
    assert record['authority_classifications']['reference']['telemetry_category'] == 'cumulative_counter'
    # A second preview with the returned mapping keeps the original exclusion evidence.
    second = client.post(url + '/mapping-preview', json=preview['mapping']).json()
    assert second['exclusions'] == preview['exclusions']
    assert client.post(url + '/approve-mapping', json={'preview_id': second['id'], 'confirmed': True}).status_code == 200
    result = client.post(url + '/runs')
    assert result.status_code == 201, result.text
    run_url = '/api/runs/' + result.json()['id']
    run = client.get(run_url).json()
    assert run['status'] == full_result()['status']
    assert run['response']['result'] == full_result()
    assert len(run['input']['signals']) == 17
    assert len(run['mapping']['signals']) == 18
    assert run['input']['rows'][0]['timestamp'] == '2026-02-01 00:00:00'
    assert run['input']['reference']['rows'][0]['timestamp'] == '2026-01-01 00:00:00'
    for key in ('validation', 'reference_validation'):
        assert 'energy_total_kwh' in [s['column'] for s in run[key]['signals']]
    assert run['source']['sha256'] == hashlib.sha256(sources[1][1]).hexdigest()
    assert run['reference_source']['sha256'] == hashlib.sha256(sources[0][1]).hexdigest()
    review = client.post(run_url + '/reviews', json={'reviewer': 'Test', 'evidence_reviewed': True})
    assert review.status_code == 201
    report_url = '/api/reviews/' + review.json()['id'] + '/report'
    report = client.get(report_url).content
    assert EXCLUSION_REASON.encode() in report and b'cumulative_counter' in report
    evidence = client.get(run_url + '/evidence').content
    assert client.get(existing_url).content == before
    for sid, raw in sources:
        assert client.get('/api/sources/' + sid + '/original').content == raw
    client.post(url + '/source?filename=replacement.csv&role=comparison', content=sources[0][1])
    assert 'preview' not in client.get(url).json()
    assert client.get(run_url + '/evidence').content == evidence
    assert client.get(report_url).content == report


@pytest.mark.parametrize('mode,reference,comparison,commit,excluded', [
    ('paired', 'cumulative_counter', 'cumulative_counter', authority.SUPPORTED_COMMIT, True),
    ('single', 'cumulative_counter', 'cumulative_counter', authority.SUPPORTED_COMMIT, False),
    ('paired', 'equipment_process', 'equipment_process', authority.SUPPORTED_COMMIT, False),
    ('paired', None, 'cumulative_counter', authority.SUPPORTED_COMMIT, False),
    ('paired', 'counter', 'counter', authority.SUPPORTED_COMMIT, False),
    ('paired', 'cumulative_counter', 'equipment_process', authority.SUPPORTED_COMMIT, False),
    ('paired', 'cumulative_counter', 'cumulative_counter', 'unreviewed-pin', False),
])
def test_only_explicit_paired_classifications_under_known_contract(mode, reference, comparison, commit, excluded):
    # An opaque identity proves the App does not use total/kwh name heuristics.
    mapping = {'signals': [dict(column='opaque', meaning='opaque', unit='dimensionless', include=True, reason='')]}
    response = {'identity': {**IDENTITY, 'commit': commit}, 'catalog': {
        'reference': {'opaque': {'telemetry_category': reference}}, 'comparison': {'opaque': {'telemetry_category': comparison}}}}
    records = exclude_unsupported_counters({'mode': mode}, mapping, response, 'input-hash')
    assert bool(records) == excluded
    assert mapping['signals'][0]['include'] == (not excluded)


def test_name_alone_and_client_reason_cannot_supply_authority_evidence():
    mapping = {'signals': [dict(column='energy_total_kwh', meaning='energy_total_kwh', unit='kWh', include=True, reason='')]}
    response = {'identity': IDENTITY, 'catalog': {'reference': {}, 'comparison': {}}}
    assert exclude_unsupported_counters({'mode': 'paired'}, mapping, response, 'hash') == []
    assert mapping['signals'][0]['include']
    mapping['signals'][0].update(include=False, reason=EXCLUSION_REASON)
    assert exclude_unsupported_counters({'mode': 'paired'}, mapping, response, 'hash') == []


def test_reduced_preview_identity_change_rejected(client, monkeypatch):
    url, mapping, _ = wwtp_pair(client)
    def call(payload, operation):
        return {'identity': IDENTITY if len(payload['signals']) == 18 else {**IDENTITY, 'adapter_sha256': 'changed'}, 'catalog': catalog(payload)}
    monkeypatch.setattr(authority, 'call', call)
    assert client.post(url + '/mapping-preview', json=mapping).status_code == 503
    assert 'preview' not in client.get(url).json()


def test_counter_only_pair_requires_at_least_one_supported_signal(client, monkeypatch):
    url, mapping, _ = wwtp_pair(client)
    for s in mapping['signals']:
        if s['column'] != 'energy_total_kwh':
            s.update(include=False, reason='Operator exclusion')
    monkeypatch.setattr(authority, 'call', lambda payload, operation: {'identity': IDENTITY, 'catalog': catalog(payload)})
    result = client.post(url + '/mapping-preview', json=mapping)
    assert result.status_code == 422
    assert 'Include 1–24 signals' in result.text


def test_reduced_catalog_still_must_match_analysis(client, monkeypatch):
    url, mapping, _ = wwtp_pair(client)
    monkeypatch.setattr(authority, 'identity', lambda: IDENTITY)
    def call(payload, operation='analyze'):
        result = {'identity': IDENTITY, 'catalog': catalog(payload)}
        if operation == 'analyze':
            result['catalog']['comparison']['influent_flow_mgd']['telemetry_category'] = 'unknown'
            result['result'] = full_result()
        return result
    monkeypatch.setattr(authority, 'call', call)
    preview = client.post(url + '/mapping-preview', json=mapping).json()
    client.post(url + '/approve-mapping', json={'preview_id': preview['id'], 'confirmed': True})
    executed = client.post(url + '/runs').json()
    assert executed['status'] == 'failed'
    assert 'classification changed since approval' in executed['error']
