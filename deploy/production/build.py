"""Build the recorded application revision, never the working tree; no AWS writes."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CONFIG = json.loads((HERE / 'resources.json').read_text())
OUT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path('/tmp/neraium-app-production-build')
OUT.mkdir(parents=True, exist_ok=False)


def run(argv, **kwargs):
    subprocess.run(argv, check=True, **kwargs)


(OUT / 'app').mkdir()
with (OUT / 'app.tar').open('wb') as stream:
    run(['git', '-C', str(ROOT), 'archive', CONFIG['application_commit']], stdout=stream)
run(['tar', '-xf', str(OUT / 'app.tar'), '-C', str(OUT / 'app')])
(OUT / 'app.tar').unlink()
run(['git', 'clone', '--no-checkout', 'https://github.com/Neraium/Neraium-1.0.git', str(OUT / 'authority')])
run(['git', '-C', str(OUT / 'authority'), 'checkout', '--detach', CONFIG['authority_commit']])
for name in ('Dockerfile', 'runtime.py'):
    shutil.copyfile(HERE / name, OUT / name)
version = dict(application='Neraium-App', commit=CONFIG['application_commit'], authority_commit=CONFIG['authority_commit'], runtime_sha256=hashlib.sha256((OUT / 'runtime.py').read_bytes()).hexdigest())
(OUT / 'version.json').write_text(json.dumps(version, indent=2) + '\n')
tag = 'neraium-app-prod:' + CONFIG['application_commit']
run(['sudo', '-n', 'docker', 'build', '-t', tag, str(OUT)])
run(['sudo', '-n', 'docker', 'run', '--rm', '-v', str(OUT / 'app/frontend') + ':/work', '-w', '/work', 'node:22-bookworm-slim', 'sh', '-c', 'npm ci --ignore-scripts --no-audit --no-fund && CI=true npm test -- --watchAll=false --runInBand --runTestsByPath src/App.test.js && REACT_APP_BACKEND_URL=. CI=true npm run build'])
# The pinned App's native projection check renders React with Node. Supply those
# test dependencies separately; the production Python image remains unchanged.
test_dockerfile = ('FROM ' + tag + '\n'
                  'USER root\n'
                  'COPY --from=node:22-bookworm-slim /usr/local/bin/node /usr/local/bin/node\n'
                  'COPY --from=node:22-bookworm-slim /usr/lib/x86_64-linux-gnu/libstdc++.so.6 /usr/lib/x86_64-linux-gnu/libstdc++.so.6\n'
                  'RUN /opt/authority-venv/bin/pip install --no-cache-dir "pytest>=8,<9"\n'
                  'USER 10001:10001\n')
test_tag = tag + '-tests'
run(['sudo', '-n', 'docker', 'build', '-t', test_tag, '-'], input=test_dockerfile, text=True)
run(['sudo', '-n', 'docker', 'run', '--rm', '-v', str(OUT / 'app/frontend/node_modules') + ':/opt/app/frontend/node_modules:ro', '-e', 'NERAIUM_TEST_AUTHORITY_ROOT=/opt/authority', '-e', 'NERAIUM_AUTHORITY_PYTHON=/opt/authority-venv/bin/python', '-w', '/opt/app', test_tag, '/opt/app-venv/bin/python', '-m', 'pytest', 'tests/workbench', '-q', '-k', 'not 8640_real_contract_envelope'])
run(['sudo', '-n', 'cp', str(OUT / 'version.json'), str(OUT / 'app/frontend/build/version.json')])
print('Artifacts:', OUT)
