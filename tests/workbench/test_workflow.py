"""Small contract tests. Stubbed responses test transport, never analytical accuracy."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess

from fastapi.testclient import TestClient
import pytest

from backend.workbench import api, authority, intake, store

RAW = b'time,flow,pressure\n2026-01-01T00:00:00Z,1,2\n2026-01-01T00:01:00Z,,3\n2026-01-01T00:02:00Z,3,4\n'
IDENTITY = {'commit': authority.SUPPORTED_COMMIT, 'adapter_contract': authority.CONTRACT}

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('NERAIUM_WORKBENCH_DATA', str(tmp_path / 'data'))
    monkeypatch.delenv('NERAIUM_WORKBENCH_TOKEN', raising=False)
    return TestClient(api.app)


def create(client, raw=RAW):
    response = client.post('/api/evaluations', json={'customer': '<script>client</script>', 'facility': 'Plant', 'system': 'Loop', 'scope': 'Historical relationship review'})
    assert response.status_code == 201, response.text
    eid = response.json()['id']
    response = client.post(f'/api/evaluations/{eid}/source?filename=source.csv', content=raw)
    assert response.status_code == 201, response.text
    return eid, response.json()['source_id']


def mapping():
    return {'context': 'Supplied loop telemetry; interventions unknown', 'signals': [
        {'column': s, 'include': True, 'meaning': s, 'unit': '', 'reason': ''} for s in ['flow', 'pressure']], 'start': '', 'end': ''}


def stub(monkeypatch, status='limited'):
    monkeypatch.setattr(authority, 'identity', lambda: IDENTITY)
    def call(payload, operation='analyze'):
        value = {'identity': IDENTITY, 'catalog': {'flow': {'engineering_units': None}}, 'runtime': {'python': 'test'}}
        if operation == 'analyze':
            assert payload['rows'][1]['flow'] is None
            value['result'] = {'engine': {'name': 'neraium_sii', 'version': 'v2'}, 'status': status,
                               'findings': [], 'uncertainty': {'limitations': ['Insufficient history']}}
        return value
    monkeypatch.setattr(authority, 'call', call)


def approve(client, eid):
    r = client.post(f'/api/evaluations/{eid}/validate', json={'timestamp_column': 'time', 'timestamp_mode': 'iso'})
    assert r.status_code == 200, r.text
    r = client.post(f'/api/evaluations/{eid}/mapping-preview', json=mapping())
    assert r.status_code == 200, r.text
    r = client.post(f'/api/evaluations/{eid}/approve-mapping', json={'preview_id': r.json()['id'], 'confirmed': True})
    assert r.status_code == 200, r.text


def test_token_free_workbench_and_retired_routes(client):
    assert client.get('/api/evaluations').status_code == 200
    for path in ['/api/demo/pronostia', '/api/playback/status', '/api/customers', '/api/systems', '/api/neraium/state/test']:
        assert client.get(path).status_code == 404
    assert client.get('/api/evaluations').headers['cache-control'] == 'no-store'


def test_source_bytes_immutable_across_replacement(client):
    eid, sid = create(client)
    client.post(f'/api/evaluations/{eid}/source?filename=new.csv', content=RAW.replace(b',3,4', b',5,6'))
    assert client.get(f'/api/sources/{sid}/original').content == RAW
    with store.connect() as db:
        assert store.get(db, 'sources', sid)['sha256'] == hashlib.sha256(RAW).hexdigest()


@pytest.mark.parametrize('raw', [b't,t\n1,2\n', b't,x\n1,2,3\n', b't,x\n'])
def test_malformed_csv_rejected(raw):
    with pytest.raises(ValueError): intake.parse(raw, 'x.csv')


@pytest.mark.parametrize('times', [
    ['2026-01-01T00:00:00', '2026-01-01T00:01:00'],
    ['2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z'],
    ['2026-01-01T00:02:00Z', '2026-01-01T00:01:00Z'],
])
def test_invalid_or_ambiguous_time_blocks_analysis(times):
    table = {'columns': ['t', 'flow'], 'rows': [{'t': t, 'flow': 1} for t in times]}
    assert not intake.validate(table, 't', 'iso')['eligible_timestamps']


def test_json_tsv_missing_and_epoch():
    tsv = intake.parse(b't\tx\n1000\t\n2000\t2\n', 'x.tsv')
    quality = intake.validate(tsv, 't', 'epoch_milliseconds')
    assert quality['start'] == '1970-01-01T00:00:01+00:00'
    assert quality['signals'][0]['missing_count'] == 1
    table = intake.parse(b'[{"t":1000,"x":NaN},{"t":2000,"x":2}]', 'x.json')
    assert intake.validate(table, 't', 'epoch_milliseconds')['signals'][0]['invalid_count'] == 1


def test_no_mapping_or_authority_no_analysis(client, monkeypatch):
    eid, _ = create(client)
    assert client.post(f'/api/evaluations/{eid}/runs').status_code == 409
    client.post(f'/api/evaluations/{eid}/validate', json={'timestamp_column': 'time', 'timestamp_mode': 'iso'})
    monkeypatch.delenv('NERAIUM_AUTHORITY_ROOT', raising=False)
    assert client.post(f'/api/evaluations/{eid}/mapping-preview', json=mapping()).status_code == 503


def test_mapping_must_include_all_columns_and_explain_exclusions():
    table = intake.parse(RAW, 'x.csv'); validation = intake.validate(table, 'time', 'iso')
    m = mapping(); m['signals'].pop()
    with pytest.raises(ValueError): intake.analysis_input(table, validation, m)
    m = mapping(); m['signals'][0]['include'] = False
    with pytest.raises(ValueError): intake.analysis_input(table, validation, m)


def test_revision_invalidates_approval(client, monkeypatch):
    stub(monkeypatch); eid, _ = create(client); approve(client, eid)
    client.post(f'/api/evaluations/{eid}/validate', json={'timestamp_column': 'time', 'timestamp_mode': 'iso'})
    assert client.post(f'/api/evaluations/{eid}/runs').status_code == 409


def test_limited_result_report_escaping_and_provenance(client, monkeypatch):
    stub(monkeypatch); eid, _ = create(client); approve(client, eid)
    response = client.post(f'/api/evaluations/{eid}/runs')
    assert response.status_code == 201, response.text
    rid = response.json()['id']; run = client.get(f'/api/runs/{rid}').json()
    assert run['status'] == 'limited' and run['response']['result']['findings'] == []
    assert run['input_sha256'] == api.digest(run['input'])
    assert run['result_sha256'] == api.digest(run['response']['result'])
    evidence = client.get(f'/api/runs/{rid}/evidence').content
    rejected = client.post(f'/api/runs/{rid}/reviews', json={'reviewer': 'Analyst', 'evidence_reviewed': False})
    assert rejected.status_code == 409
    reviewed = client.post(f'/api/runs/{rid}/reviews', json={'reviewer': 'Analyst', 'evidence_reviewed': True})
    assert reviewed.status_code == 201, reviewed.text
    review = reviewed.json()
    html = client.get(f"/api/reviews/{review['id']}/report").content
    assert b'<script>client</script>' not in html and b'&lt;script&gt;client&lt;/script&gt;' in html
    assert b'Insufficient history' in html and b'read-only' in html
    assert hashlib.sha256(html).hexdigest() == review['report_sha256']
    client.post(f'/api/evaluations/{eid}/source?filename=other.csv', content=RAW)
    assert client.get(f'/api/runs/{rid}/evidence').content == evidence
    assert client.get(f"/api/reviews/{review['id']}/report").content == html


def test_engine_failure_never_manufactures_report(client, monkeypatch):
    stub(monkeypatch); eid, _ = create(client); approve(client, eid)
    def fail(*args): raise authority.AuthorityError('Authority failed')
    monkeypatch.setattr(authority, 'call', fail)
    run = client.post(f'/api/evaluations/{eid}/runs').json()
    assert run['status'] == 'failed'
    assert 'response' not in client.get(f"/api/runs/{run['id']}").json()
    assert client.post(f"/api/runs/{run['id']}/reviews", json={'reviewer': 'Analyst', 'evidence_reviewed': True}).status_code == 409


def test_authority_changed_since_preview_blocks_run(client, monkeypatch):
    stub(monkeypatch); eid, _ = create(client); approve(client, eid)
    monkeypatch.setattr(authority, 'identity', lambda: {**IDENTITY, 'adapter_contract': 'changed'})
    assert client.post(f'/api/evaluations/{eid}/runs').status_code == 409


def test_authority_malformed_response_is_rejected(monkeypatch):
    monkeypatch.setattr(authority, 'identity', lambda: IDENTITY)
    monkeypatch.setenv('NERAIUM_AUTHORITY_ROOT', '/unused')
    monkeypatch.setattr(subprocess, 'run', lambda *a, **k: subprocess.CompletedProcess([], 0, '[]', ''))
    with pytest.raises(authority.AuthorityError): authority.call({})


def test_external_storage_required(monkeypatch):
    monkeypatch.setenv('NERAIUM_WORKBENCH_DATA', str(Path(__file__).resolve().parents[2] / 'data'))
    with pytest.raises(ValueError): store.connect()


def test_old_review_cannot_advance_replaced_source(client, monkeypatch):
    stub(monkeypatch); eid, _ = create(client); approve(client, eid)
    rid = client.post(f'/api/evaluations/{eid}/runs').json()['id']
    client.post(f'/api/evaluations/{eid}/source?filename=replacement.csv', content=RAW)
    assert client.post(f'/api/runs/{rid}/reviews', json={'reviewer': 'Analyst', 'evidence_reviewed': True}).status_code == 201
    assert client.get(f'/api/evaluations/{eid}').json()['stage'] == 'VALIDATION'


def test_source_column_whitespace_preserved(client):
    eid, _ = create(client, RAW.replace(b'time,flow', b' time , flow '))
    response = client.post(f'/api/evaluations/{eid}/validate', json={'timestamp_column': ' time ', 'timestamp_mode': 'iso'})
    assert response.status_code == 200, response.text
    assert response.json()['signals'][0]['column'] == ' flow '
    assert api.Signal(column=' flow ', include=False).column == ' flow '


def test_duplicate_json_cells_rejected():
    with pytest.raises(ValueError, match='duplicate'):
        intake.parse(b'[{"t":1,"x":2,"x":3}]', 'x.json')


@pytest.mark.skipif(not os.getenv('NERAIUM_TEST_AUTHORITY_ROOT'), reason='Pinned external authority integration is explicitly opt-in')
def test_pinned_authority_full_workflow(client, monkeypatch):
    monkeypatch.setenv('NERAIUM_AUTHORITY_ROOT', os.environ['NERAIUM_TEST_AUTHORITY_ROOT'])
    monkeypatch.setenv('NERAIUM_AUTHORITY_COMMIT', authority.SUPPORTED_COMMIT)
    raw = ('time,flow,pressure\n' + ''.join(f'2026-01-01T00:{i:02}:00Z,{10+i%3},{20+i%3}\n' for i in range(24))).encode()
    eid, _ = create(client, raw); approve(client, eid)
    response = client.post(f'/api/evaluations/{eid}/runs')
    assert response.status_code == 201, response.text
    run = client.get(f"/api/runs/{response.json()['id']}").json()
    assert run['status'] in {'complete', 'limited'}, run.get('error')
    assert run['response']['result']['processing_trace']['modules_failed'] == []
    assert run['response']['identity']['commit'] == authority.SUPPORTED_COMMIT
    assert run['response']['result']['engine'] == {'name': 'neraium_sii', 'version': 'v2'}
    assert len(run['input']['rows']) == 24
    reviewed = client.post(f"/api/runs/{run['id']}/reviews", json={'reviewer': 'Integration test', 'evidence_reviewed': True})
    assert reviewed.status_code == 201, reviewed.text
    assert client.get(f"/api/reviews/{reviewed.json()['id']}/report").status_code == 200


def test_report_keeps_long_evidence_and_timing(client, monkeypatch):
    from backend.workbench import report
    stub(monkeypatch); eid, _ = create(client); approve(client, eid)
    rid = client.post(f'/api/evaluations/{eid}/runs').json()['id']
    run = client.get(f'/api/runs/{rid}').json()
    # Transport fixtures only: no assertions about analytical correctness.
    result = run['response']['result']
    result['findings'] = [{'classification': 'test classification', 'evidence': 'x' * 3600,
                           'consequence_provenance': 'test-source-reference'}]
    result['relationship_analysis'] = {'top_relationship_changes': [
        {'evidence_refs': ['test-relationship-reference'], 'time_window': 'test-window'}]}
    result['persistence_analysis'] = {'timing_evidence': 'test-timing-reference'}
    result['uncertainty']['additional_evidence_limit'] = 'test-uncertainty-reference'
    html = report.render(run, {'reviewer': 'Analyst', 'created_at': 'test-review-time'})
    for value in ('x' * 3600, 'test classification', 'test-source-reference',
                  'test-relationship-reference', 'test-window', 'test-timing-reference',
                  'test-uncertainty-reference'):
        assert value in html
    assert 'omitted here for report brevity' not in html


def test_authority_default_pin_and_explicit_mismatch(monkeypatch):
    monkeypatch.setenv('NERAIUM_AUTHORITY_ROOT', '/unused')
    monkeypatch.delenv('NERAIUM_AUTHORITY_COMMIT', raising=False)
    monkeypatch.setattr(subprocess, 'check_output', lambda args, **kw:
                        authority.SUPPORTED_COMMIT if 'rev-parse' in args else '')
    assert authority.identity()['commit'] == authority.SUPPORTED_COMMIT
    monkeypatch.setenv('NERAIUM_AUTHORITY_COMMIT', '0' * 40)
    with pytest.raises(authority.AuthorityError, match='not been contract-validated'):
        authority.identity()
    monkeypatch.setenv('NERAIUM_AUTHORITY_COMMIT', '')
    monkeypatch.setattr(subprocess, 'check_output', lambda args, **kw: '0' * 40 if 'rev-parse' in args else '')
    with pytest.raises(authority.AuthorityError, match='must match the pinned commit'):
        authority.identity()
