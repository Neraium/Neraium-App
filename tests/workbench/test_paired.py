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
            response['result'] = dict(status='limited', reference_baseline={'test': 'stub'}, relationship_analysis={'top_relationship_changes': []}, limitations=['No paired onset supplied'], processing_trace={})
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
    assert 'Reference period/data' in html and 'Comparison period/data' in html and 'No paired onset supplied' in html
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
    raw = ('time,flow,pressure\n' + ''.join(f'{i*900},{10+i%7},{20+2*(i%7)}\n' for i in range(48))).encode()
    table = intake.parse(raw, 'neutral.csv'); quality = intake.validate(table, 'time', 'epoch_seconds')
    payload = intake.paired_input(table, table, quality, quality, paired_mapping())
    result = authority.call({**payload, 'run_id': 'paired-contract-test'})
    assert result['identity']['commit'] == authority.SUPPORTED_COMMIT
    assert result['result']['status'] == 'limited'
    assert result['result']['reference_baseline']['dataset_id'] == 'paired-contract-test-reference'
    assert result['result']['processing_trace']['baseline_artifacts_reused'] == 1
    assert len(payload['reference']['rows']) == len(payload['rows']) == 48


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
    def baseline(**kw):
        calls['baseline'] = kw
        return {'candidate_model': {'exact': 'model'}, 'baseline_suitability': {'eligible_for_activation': True}}
    def compare(model, rows, **kw):
        calls['compare'] = (model, rows)
        return [{'evidence': 'authority-only'}]
    def evaluate(**kw): calls['single'] = kw; return {'authority': True}
    module('app.services.behavioral_baseline', build_behavioral_baseline=baseline)
    module('app.services.upload_jobs', _comparison_relationship_changes=compare)
    module('app.engine.sii_engine', evaluate_sii=evaluate)
    monkeypatch.setattr(sys, 'argv', ['worker', '/unused', 'analyze'])
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(payload)))
    output = io.StringIO(); monkeypatch.setattr(sys, 'stdout', output)
    monkeypatch.setattr(authority_worker.importlib.metadata, 'distributions', lambda: [])
    authority_worker.main()
    response = json.loads(output.getvalue())
    if paired:
        assert 'single' not in calls
        assert calls['baseline']['rows'] == payload['reference']['rows']
        assert calls['baseline']['filename'] == 'reference'
        assert calls['baseline']['approval_required'] is True
        assert calls['compare'] == ({'exact': 'model'}, payload['rows'])
        assert response['result']['relationship_analysis']['top_relationship_changes'] == [{'evidence': 'authority-only'}]
    else:
        assert calls['single']['rows'] == payload['rows']
        assert calls['single']['config']['temporal_config']['max_rows'] == len(payload['rows'])


def test_paired_malformed_contract(monkeypatch):
    import json
    import subprocess
    monkeypatch.setattr(authority, 'identity', lambda: IDENTITY)
    monkeypatch.setenv('NERAIUM_AUTHORITY_ROOT', '/unused')
    response = dict(contract=authority.CONTRACT, operation='analyze', catalog={}, runtime={}, result={
        'comparison_contract': 'neraium-workbench-paired.v1', 'status': 'limited',
        'reference_baseline': {}, 'relationship_analysis': None})
    monkeypatch.setattr(subprocess, 'run', lambda *a, **kw: subprocess.CompletedProcess([], 0, json.dumps(response), ''))
    with pytest.raises(authority.AuthorityError, match='paired'):
        authority.call({'mode': 'paired'})


def test_unsuitable_reference_error(monkeypatch):
    import subprocess
    monkeypatch.setattr(authority, 'identity', lambda: IDENTITY)
    monkeypatch.setenv('NERAIUM_AUTHORITY_ROOT', '/unused')
    monkeypatch.setattr(subprocess, 'run', lambda *a, **kw: subprocess.CompletedProcess(
        [], 1, '', 'ValueError: Authority rejected the supplied reference as unsuitable.'))
    with pytest.raises(authority.AuthorityError, match='no comparison was run'):
        authority.call({'mode': 'paired'})
