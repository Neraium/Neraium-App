"""Clean authority native producer → App storage, report and React projection.

The authority's own qualified producer fixture supplies the finding. This is a
projection test; the separate paired integration tests exercise evaluate_sii.
"""
from contextlib import closing
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from backend.workbench import authority, report, store
from test_report import fixture
from test_workflow import client


@pytest.mark.skipif(not os.getenv('NERAIUM_TEST_AUTHORITY_ROOT'), reason='Opt-in clean authority native projection')
def test_real_authority_calendar_finding_projection(client, monkeypatch, tmp_path):
    root = Path(os.environ['NERAIUM_TEST_AUTHORITY_ROOT']).resolve()
    monkeypatch.setenv('NERAIUM_AUTHORITY_ROOT', str(root))
    identity = authority.identity()
    script = '''
import contextlib, json, sys
from pathlib import Path
root, runtime = map(Path, sys.argv[1:])
sys.path[:0] = [str(root), str(root / 'backend'), str(root / 'shared/neraium-intelligence/src'), str(root / 'tests')]
with contextlib.redirect_stdout(sys.stderr):
    from db.migrations.apply_runtime import migrate_sqlite
    migrate_sqlite(runtime)
    from test_relationship_authority import produce, source
    from test_overconservatism_remediation import mode_for
    from test_scoped_product_projection import transported
    produced = produce()
    mode = mode_for('calendar')
    produced[0]['operating_mode'] = mode
    native = source(produced)
    native['data_quality']['operating_mode'] = mode
    native['relationship_model']['operating_mode'] = mode
    canonical = transported(native)['analysis_result']
    assert mode['calendar_comparison']['week_band_veto'] is False
json.dump({'status': canonical['status'], 'analysis_result': canonical,
           'findings': canonical['insights'], 'relationship_analysis': native['relationship_model']},
          sys.stdout, allow_nan=False)
'''
    env = {**os.environ, 'NERAIUM_ENV': 'development', 'PYTHONDONTWRITEBYTECODE': '1',
           'NERAIUM_RUNTIME_DIR': str(tmp_path / 'runtime'), 'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1'}
    process = subprocess.run([os.getenv('NERAIUM_AUTHORITY_PYTHON', sys.executable), '-I', '-B', '-c', script,
                              str(root), str(tmp_path / 'runtime')], cwd=tmp_path, env=env,
                             text=True, capture_output=True, timeout=120)
    assert process.returncode == 0, process.stderr
    result = json.loads(process.stdout)
    findings = result['analysis_result']['relationship_findings']
    supported = next(f for f in findings if f['classification']['type'] == 'unexplained_systemic_change')
    assert supported['persistence']['persistent'] is True
    assert all(f['classification']['type'] != 'unexplained_systemic_change' for f in result['findings'])
    assert authority.identity() == identity

    # Seed a transport fixture with the untouched native result, then use the
    # real App read/review endpoints. No analytical result is fabricated.
    evaluation = client.post('/api/evaluations', json={'mode': 'paired'}).json()
    run = fixture()
    run.update(evaluation_id=evaluation['id'], evaluation=evaluation, status=result['status'])
    run['response'] = {'identity': identity, 'result': result}
    with closing(store.connect()) as db, db:
        db.execute('INSERT INTO runs VALUES (?,?,?)', (run['id'], evaluation['id'], store.encode(run)))
    evidence = client.get('/api/runs/run/evidence')
    strict = lambda raw: json.loads(raw, parse_constant=lambda token: pytest.fail('Non-finite JSON: ' + token))
    assert strict(evidence.content)['response']['result'] == result
    assert report.project(result)['governed_findings'] == findings
    assert 'Persistent relationship change was observed' in report.project(result)['summary']
    review = client.post('/api/runs/run/reviews', json={'reviewer': 'Native authority projection check', 'evidence_reviewed': True})
    assert review.status_code == 201, review.text
    html = client.get('/api/reviews/' + review.json()['id'] + '/report').text
    assert supported['classification']['label'] in html
    assert '<dt>Relationship persistence</dt><dd>Confirmed</dd>' in html
    assert supported['persistence']['summary'] in html
    assert 'does not establish a persistent relationship change' not in html
    assert client.get('/api/runs/run/evidence').content == evidence.content

    # Execute the actual React component with the native result. Babel supplies
    # the same JSX/module transform used by the focused frontend tests.
    frontend = Path(__file__).resolve().parents[2] / 'frontend'
    render_script = '''
const fs = require('fs'), path = require('path'), Module = require('module');
const base = process.argv[1];
const dependency = name => require(path.join(base, 'node_modules', name));
const React = dependency('react'), {renderToStaticMarkup} = dependency('react-dom/server');
const filename = path.join(base, 'src/EvaluationResult.js');
const code = dependency('@babel/core').transformSync(fs.readFileSync(filename, 'utf8'), {
  filename, babelrc: false, configFile: false,
  presets: [[dependency('@babel/preset-react'), {runtime: 'automatic'}]],
  plugins: [dependency('@babel/plugin-transform-modules-commonjs')]
}).code;
const component = new Module(filename, module);
component.filename = filename; component.paths = Module._nodeModulePaths(path.dirname(filename));
component._compile(code, filename);
const result = JSON.parse(fs.readFileSync(0, 'utf8'));
process.stdout.write(JSON.stringify({
  findings: component.exports.projectedFindings(result),
  html: renderToStaticMarkup(React.createElement(component.exports.default, {run: {status: result.status, response: {result}}}))
}));
'''
    rendered = subprocess.run(['node', '-e', render_script, str(frontend)], input=store.encode(result),
                              capture_output=True, text=True, timeout=30, cwd=tmp_path)
    assert rendered.returncode == 0, rendered.stderr
    output = strict(rendered.stdout)
    assert next(f for f in output['findings'] if f['id'] == supported['id']) == supported
    assert sum(f['id'] == supported['id'] for f in output['findings']) == 1
    assert supported['classification']['label'] in output['html']
    assert 'Relationship persistence</dt><dd>Confirmed' in output['html']
    assert authority.identity() == identity
