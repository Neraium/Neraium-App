"""Paired transport/compatibility tests; generated data only."""
import os
from copy import deepcopy
import hashlib

import pytest

from backend.workbench import api, authority, intake
from test_workflow import client, mapping, RAW, IDENTITY


def pair(client):
    eid = client.post('/api/evaluations', json=dict(customer='Test', facility='Plant', system='Loop', scope='Review', mode='paired')).json()['id']
    originals = {}
    for role in ('reference', 'comparison'):
        r = client.post(f'/api/evaluations/{eid}/source?filename={role}.csv&role={role}', content=RAW)
        assert r.status_code == 201, r.text
        originals[role] = r.json()['source_id']
        r = client.post(f'/api/evaluations/{eid}/validate?role={role}', json=dict(timestamp_column='time', timestamp_mode='iso'))
        assert r.status_code == 200, r.text
    return eid, originals


def paired_mapping():
    m = mapping(); m['pair_confirmed'] = True
    for s in m['signals']: s['unit'] = 'dimensionless'
    return m


def test_paired_workflow(client, monkeypatch):
    seen = []
    monkeypatch.setattr(authority, 'identity', lambda: IDENTITY)
    def call(payload, operation='analyze'):
        seen.append(deepcopy(payload))
        response = dict(identity=IDENTITY, catalog={'reference': {}, 'comparison': {}})
        if operation == 'analyze':
            response['result'] = full_result()
        return response
    monkeypatch.setattr(authority, 'call', call)
    eid, originals = pair(client)
    url = f'/api/evaluations/{eid}'
    m = paired_mapping()
    assert client.post(url + '/mapping-preview', json={**m, 'pair_confirmed': False}).status_code == 422
    preview = client.post(url + '/mapping-preview', json=m)
    assert preview.status_code == 200, preview.text
    assert client.post(url + '/approve-mapping', json=dict(preview_id=preview.json()['id'], confirmed=True)).status_code == 200
    r = client.post(url + '/runs'); assert r.status_code == 201, r.text
    rid = r.json()['id']; run = client.get(f'/api/runs/{rid}').json()
    assert run['input']['reference']['rows'] == run['input']['rows']
    assert run['reference_source']['id'] == originals['reference']
    assert run['source']['id'] == originals['comparison']
    for sid in originals.values(): assert client.get(f'/api/sources/{sid}/original').content == RAW
    assert run['reference_source']['sha256'] == hashlib.sha256(RAW).hexdigest()
    assert run['input_sha256'] == api.digest(run['input'])
    assert 'filename' not in seen[-1] and 'customer' not in seen[-1]
    review = client.post(f'/api/runs/{rid}/reviews', json=dict(reviewer='Test', evidence_reviewed=True)).json()
    html = client.get(f"/api/reviews/{review['id']}/report").text
    assert 'Reference period/data' in html and 'Comparison period/data' in html and 'supplied-reference-v1' in html
    assert 'authority-only-onset' in html
    assert run['response']['result'] == full_result()
    assert client.get(f'/api/runs/{rid}/evidence').json()['response']['result'] == full_result()
    evidence = client.get(f'/api/runs/{rid}/evidence').content
    client.post(url + '/source?filename=replacement.csv&role=reference', content=RAW)
    assert client.post(url + '/runs').status_code == 409
    assert client.get(f'/api/runs/{rid}/evidence').content == evidence
    assert client.get(f"/api/reviews/{review['id']}/report").text == html


@pytest.mark.parametrize('issue', ['schema', 'unit', 'timestamps', 'excluded', 'window', 'confirmation'])
def test_pair_incompatible(issue):
    ref = intake.parse(RAW, 'r.csv'); comp = deepcopy(ref)
    m = paired_mapping()
    if issue == 'schema': comp['columns'].append('other'); comp['rows'][0]['other'] = 1
    if issue == 'unit': m['signals'][0]['unit'] = ''
    if issue == 'timestamps': comp['rows'][1]['time'] = 'invalid'
    if issue == 'excluded': m['signals'][0]['include'] = False
    if issue == 'window': m['start'] = '2026-01-01T00:00:00Z'
    if issue == 'confirmation': m['pair_confirmed'] = False
    with pytest.raises(ValueError):
        intake.paired_input(ref, comp, intake.validate(ref, 'time', 'iso'), intake.validate(comp, 'time', 'iso'), m)


@pytest.mark.parametrize('count', [8640, 10000, 10001])
def test_intake_limit(count):
    raw = ('time,flow\n' + ''.join(f'{i*900},1\n' for i in range(count))).encode()
    if count > intake.MAX_ROWS:
        with pytest.raises(ValueError): intake.parse(raw, 'x.csv')
    else:
        table = intake.parse(raw, 'x.csv')
        assert len(table['rows']) == count
        assert intake.validate(table, 'time', 'epoch_seconds')['eligible_timestamps']


@pytest.mark.skipif(not os.getenv('NERAIUM_TEST_AUTHORITY_ROOT'), reason='Opt-in pinned authority')
def test_real_paired_authority(monkeypatch):
    monkeypatch.setenv('NERAIUM_AUTHORITY_ROOT', os.environ['NERAIUM_TEST_AUTHORITY_ROOT'])
    payload = generated_pair(64)
    result = authority.call({**payload, 'run_id': 'paired-contract-test'})
    assert result['identity']['commit'] == authority.SUPPORTED_COMMIT
    evidence = result['result']
    assert evidence['processing_trace']['modules_failed'] == []
    assert evidence['findings'] == evidence['analysis_result']['insights']
    assert evidence['findings']
    assert evidence['analysis_result']['evidence_index']
    assert evidence['analysis_result']['sii_evidence']['relationship_changes']
    assert evidence['temporal_analysis']['active_rows'] == 64
    assert evidence['temporal_analysis']['lead_time_estimate']['timestamp'] in [r['timestamp'] for r in payload['rows']]
    assert evidence['persistence_analysis']['adaptive_persistence']['rows_used'] == 64
    assert evidence['persistence_analysis']['adaptive_persistence']['elapsed_time_available']
    assert evidence['supplied_reference']['reference']['row_count'] == 64
    assert evidence['supplied_reference']['comparison']['row_count'] == 64


def generated_pair(count):
    import math
    tables = []
    for role in ('reference', 'comparison'):
        raw = ('time,flow,pressure,power\n' + ''.join(
            f'{(i + (129600 if role == "comparison" else 0))*60},'
            f'{80+4*math.sin(i/4)},'
            f'{40+2*math.sin(i/4) if role == "reference" else 55+2*math.cos(i*2)},'
            f'{20+math.sin(i/4) if role == "reference" else 28+math.sin(i/4)}\n'
            for i in range(count))).encode()
        tables.append(intake.parse(raw, role + '.csv'))
    m = paired_mapping()
    m['signals'].append(dict(column='power', meaning='power', unit='dimensionless', include=True, reason=''))
    return intake.paired_input(*tables, *(intake.validate(t, 'time', 'epoch_seconds') for t in tables), m)


def full_result():
    # Explicit transport fixture, not analytical evidence.
    return dict(engine={'name': 'neraium_sii', 'version': 'v2'}, status='limited',
                findings=[], analysis_result={'insights': [], 'sii_evidence': {'consequence': 'authority-only-fixture'}},
                supplied_reference={'contract_version': 'supplied-reference-v1', 'reference': {}, 'comparison': {}},
                temporal_analysis={'onset': 'authority-only-onset'}, persistence_analysis={'rows_used': 3},
                uncertainty={'limitations': ['authority-only-limitation']},
                relationship_analysis={'top_relationship_changes': []}, processing_trace={})


@pytest.mark.parametrize('paired', [False, True])
def test_worker_request_boundary(monkeypatch, paired):
    import io
    import json
    import sys
    import types
    from backend.workbench import authority_worker
    table = intake.parse(RAW, 'outcome-name-never-forwarded.csv')
    quality = intake.validate(table, 'time', 'iso')
    payload = (intake.paired_input(table, table, quality, quality, paired_mapping()) if paired
               else intake.analysis_input(table, quality, mapping()))
    payload['run_id'] = 'test'
    calls = {}
    def module(name, **functions): monkeypatch.setitem(sys.modules, name, types.SimpleNamespace(**functions))
    module('app.services.data_quality', profile_numeric_columns=lambda *a: [])
    module('app.services.telemetry_classification', build_telemetry_signal_catalog=lambda *a, **kw: {'flow': {}, 'pressure': {}})
    def evaluate(**kw): calls['evaluate'] = kw; return full_result()
    module('app.engine.sii_engine', evaluate_sii=evaluate)
    monkeypatch.setattr(sys, 'argv', ['worker', '/unused', 'analyze'])
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(payload)))
    output = io.StringIO(); monkeypatch.setattr(sys, 'stdout', output)
    monkeypatch.setattr(authority_worker.importlib.metadata, 'distributions', lambda: [])
    authority_worker.main()
    response = json.loads(output.getvalue())
    assert response['result'] == full_result()
    request = calls['evaluate']
    if paired:
        assert request['reference_rows'] == payload['reference']['rows']
        assert request['comparison_rows'] == payload['rows']
        assert request['signal_units'] == {'flow': 'dimensionless', 'pressure': 'dimensionless'}
        assert set(request['config']) == {'numeric_columns', 'engineering_priors'}
        assert 'rows' not in request and 'telemetry_signal_catalog' not in request
    else:
        assert request['rows'] == payload['rows']
        assert request['config']['temporal_config']['max_rows'] == len(payload['rows'])


def test_paired_malformed_contract(monkeypatch):
    import json
    import subprocess
    monkeypatch.setattr(authority, 'identity', lambda: IDENTITY)
    monkeypatch.setenv('NERAIUM_AUTHORITY_ROOT', '/unused')
    response = dict(contract=authority.CONTRACT, operation='analyze', catalog={}, runtime={}, result={**full_result(), 'supplied_reference': None})
    monkeypatch.setattr(subprocess, 'run', lambda *a, **kw: subprocess.CompletedProcess([], 0, json.dumps(response), ''))
    with pytest.raises(authority.AuthorityError, match='paired'):
        authority.call({'mode': 'paired'})


def test_authority_rejection_error(monkeypatch):
    import subprocess
    monkeypatch.setattr(authority, 'identity', lambda: IDENTITY)
    monkeypatch.setenv('NERAIUM_AUTHORITY_ROOT', '/unused')
    monkeypatch.setattr(subprocess, 'run', lambda *a, **kw: subprocess.CompletedProcess(
        [], 1, '', 'ValueError: paired_reference_numeric_value_required:flow'))
    with pytest.raises(authority.AuthorityError, match='no result was substituted'):
        authority.call({'mode': 'paired'})


@pytest.mark.skipif(not os.getenv('NERAIUM_TEST_AUTHORITY_ROOT'), reason='Opt-in pinned authority')
def test_8640_real_contract_envelope(monkeypatch):
    """Run the actual authority input boundary, without a large analytical replay."""
    import io
    import json
    import subprocess
    import sys
    import types
    from pathlib import Path
    from backend.workbench import authority_worker
    root = os.environ['NERAIUM_TEST_AUTHORITY_ROOT']
    monkeypatch.setenv('NERAIUM_AUTHORITY_ROOT', root)
    assert authority.identity()['commit'] == authority.SUPPORTED_COMMIT
    payload = generated_pair(8640)
    payload['run_id'] = 'envelope-test'
    captured = {}
    def evaluate(**kwargs):
        captured.update(kwargs)
        return full_result()
    monkeypatch.setitem(sys.modules, 'app.engine.sii_engine', types.SimpleNamespace(evaluate_sii=evaluate))
    monkeypatch.setitem(sys.modules, 'app.services.data_quality', types.SimpleNamespace(
        profile_numeric_columns=lambda columns, matrix: [{'column': c} for c in columns[1:]]))
    monkeypatch.setitem(sys.modules, 'app.services.telemetry_classification', types.SimpleNamespace(
        build_telemetry_signal_catalog=lambda columns, **kw: {c: {} for c in columns[1:]}))
    monkeypatch.setattr(sys, 'argv', ['worker', root, 'analyze'])
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(payload)))
    monkeypatch.setattr(sys, 'stdout', io.StringIO())
    monkeypatch.setattr(authority_worker.importlib.metadata, 'distributions', lambda: [])
    authority_worker.main()
    assert captured['reference_rows'] == payload['reference']['rows']
    assert captured['comparison_rows'] == payload['rows']
    script = """
import json, sys
from app.engine.supplied_reference import prepare_supplied_reference
args = json.load(sys.stdin)
reference, comparison, cfg, provenance = prepare_supplied_reference(**args)
assert len(reference[0]) == len(comparison[0]) == 8640
assert cfg['temporal_config'].max_rows == 12000
for role in ('reference', 'comparison'):
    assert provenance[role]['row_count'] == provenance[role]['row_end'] == 8640
    assert provenance[role]['time_start'] == args[role + '_rows'][0]['timestamp']
    assert provenance[role]['time_end'] == args[role + '_rows'][-1]['timestamp']
print('two intact 8640-row periods accepted')
"""
    env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1',
           'PYTHONPATH': str(Path(root) / 'backend') + ':' + str(Path(root) / 'shared/neraium-intelligence/src')}
    result = subprocess.run([os.getenv('NERAIUM_AUTHORITY_PYTHON', sys.executable), '-B', '-c', script],
                            input=json.dumps(captured), capture_output=True, text=True, env=env, timeout=30)
    assert result.returncode == 0, result.stderr
    assert 'two intact 8640-row periods accepted' in result.stdout
