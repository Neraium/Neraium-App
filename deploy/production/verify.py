"""Focused deployed contract check. Creates one clearly labelled synthetic evaluation."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import urllib.error
import urllib.request


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("origin")
    parser.add_argument("--token-file", required=True)
    args = parser.parse_args()
    token = Path(args.token_file).read_text().strip()
    config = json.loads(Path(__file__).with_name("resources.json").read_text())

    def request(path, data=None, raw=False, authenticated=True):
        headers = {"X-Workbench-Token": token} if authenticated else {}
        if isinstance(data, dict):
            data = json.dumps(data).encode()
            headers["Content-Type"] = "application/json"
        elif data is not None:
            headers["Content-Type"] = "application/octet-stream"
        req = urllib.request.Request(args.origin.rstrip("/") + path, data=data, headers=headers)
        with urllib.request.urlopen(req, timeout=150) as response:
            body = response.read()
            if path.startswith('/api/'):
                assert 'no-store' in response.headers['Cache-Control']
            return body if raw else json.loads(body)

    health = request('/healthz', authenticated=False)
    version = request('/version.json', authenticated=False)
    backend_version = request('/api/version')
    manifest = json.loads(Path(__file__).with_name('frontend-sha256.json').read_text())
    for path, expected in manifest.items():
        actual = request('/' + path, raw=True, authenticated=False)
        assert hashlib.sha256(actual).hexdigest() == expected, path
    for item in (health, version, backend_version):
        assert item['commit'] == config['application_commit'], item
        assert item['authority_commit'] == config['authority_commit'], item
    assert request('/api/authority')['available']
    try:
        request('/api/evaluations', authenticated=False)
        raise AssertionError('Unauthenticated API was accessible')
    except urllib.error.HTTPError as exc:
        assert exc.code == 401

    evaluation = request('/api/evaluations', dict(mode='paired', customer='DEPLOYMENT CHECK (synthetic)', facility='App production verification', system='Generated contract loop', scope='64 generated rows per period; no customer data. Verify paired transport and pinned authoritative evidence.'))
    url = '/api/evaluations/' + evaluation['id']
    hashes = {}
    for role in ('reference', 'comparison'):
        raw = ('time,flow,pressure,power\n' + ''.join(
            f'{(i + (129600 if role == "comparison" else 0))*60},'
            f'{80+4*math.sin(i/4)},'
            f'{40+2*math.sin(i/4) if role == "reference" else 55+2*math.cos(i*2)},'
            f'{20+math.sin(i/4) if role == "reference" else 28+math.sin(i/4)}\n'
            for i in range(64))).encode()
        source = request(url + f'/source?filename={role}.csv&role={role}', raw)
        original = request('/api/sources/' + source['source_id'] + '/original', raw=True)
        assert original == raw
        hashes[role] = hashlib.sha256(raw).hexdigest()
        request(url + '/validate?role=' + role, dict(timestamp_column='time', timestamp_mode='epoch_seconds'))
    mapping = dict(pair_confirmed=True, context='Generated contract fixture, same synthetic system; no physical engineering claims.', signals=[dict(column=name, include=True, meaning=name, unit='dimensionless', reason='') for name in ('flow', 'pressure', 'power')])
    preview = request(url + '/mapping-preview', mapping)
    request(url + '/approve-mapping', dict(preview_id=preview['id'], confirmed=True))
    result = request(url + '/runs', {})
    run = request('/api/runs/' + result['id'])
    assert run['status'] in ('complete', 'limited'), run['status']
    assert run['response']['identity']['commit'] == config['authority_commit']
    assert run['reference_source']['sha256'] == hashes['reference']
    assert run['source']['sha256'] == hashes['comparison']
    evidence = run['response']['result']
    assert evidence['processing_trace']['modules_failed'] == []
    assert evidence['findings'] == evidence['analysis_result']['insights']
    assert evidence['supplied_reference']['contract_version'] == 'supplied-reference-v1'
    for role in ('reference', 'comparison'):
        assert evidence['supplied_reference'][role]['row_count'] == 64
    assert request('/api/runs/' + run['id'] + '/evidence')['response']['result'] == evidence
    review = request('/api/runs/' + run['id'] + '/reviews', dict(reviewer='Deployment verification (synthetic)', evidence_reviewed=True))
    report = request('/api/reviews/' + review['id'] + '/report', raw=True).decode()
    assert 'Reference period/data' in report and 'Comparison period/data' in report
    print(json.dumps(dict(status='passed', origin=args.origin, commit=version['commit'], authority_commit=config['authority_commit'], evaluation_id=evaluation['id'], run_id=run['id'], report_id=review['id'], source_hashes=hashes), indent=2))


if __name__ == '__main__':
    main()
