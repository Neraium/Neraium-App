"""Update only the recorded App stack. Never changes DNS or other distributions."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
STATE = json.loads((HERE / 'resources.json').read_text())


def aws(*args, document=None):
    command = ['aws', *args, '--region', STATE['region'], '--output', 'json']
    if document is not None:
        command += ['--cli-input-json', json.dumps(document)]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode:
        raise SystemExit(result.stderr)
    return json.loads(result.stdout) if result.stdout.strip() else {}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('operation', choices=['frontend', 'backend', 'attach-domain'])
    parser.add_argument('--build', type=Path)
    args = parser.parse_args()
    assert aws('sts', 'get-caller-identity')['Account'] == STATE['account']
    assert STATE['distribution'] == 'E27KJ5Y66YQQBO'
    distribution = aws('cloudfront', 'get-distribution-config', '--id', STATE['distribution'])
    config = distribution['DistributionConfig']
    assert config['Comment'].startswith('Neraium-App dedicated production;')
    assert {o['Id'] for o in config['Origins']['Items']} == {'app-frontend', 'app-api'}

    if args.operation == 'frontend':
        assert args.build and args.build.is_dir(), 'Supply --build /path/to/frontend/build'
        version = json.loads((args.build / 'version.json').read_text())
        assert version['commit'] == STATE['application_commit']
        subprocess.run(['aws', 's3', 'sync', str(args.build), 's3://' + STATE['frontend_bucket'] + '/', '--region', STATE['region'], '--exclude', '*.map', '--cache-control', 'no-cache', '--only-show-errors'], check=True)
        aws('cloudfront', 'create-invalidation', '--distribution-id', STATE['distribution'], '--paths', '/*')
    elif args.operation == 'backend':
        definition = json.loads((HERE / 'task-definition.json').read_text())
        assert definition['family'] == 'neraium-app-prod'
        assert definition['containerDefinitions'][0]['image'] == STATE['ecr_repository'] + '@' + STATE['image_digest']
        registered = aws('ecs', 'register-task-definition', document=definition)['taskDefinition']['taskDefinitionArn']
        aws('ecs', 'update-service', '--cluster', STATE['cluster'], '--service', 'neraium-app-prod', '--task-definition', registered)
        STATE['task_definition'] = registered
        (HERE / 'resources.json').write_text(json.dumps(STATE, indent=2) + '\n')
    else:
        certificate = aws('acm', 'describe-certificate', '--certificate-arn', STATE['certificate'])['Certificate']
        assert certificate['Status'] == 'ISSUED', 'Certificate DNS validation must complete first. No DNS changes were made.'
        assert 'app.neraium.com' in certificate['SubjectAlternativeNames']
        config['Aliases'] = dict(Quantity=1, Items=['app.neraium.com'])
        config['ViewerCertificate'] = dict(ACMCertificateArn=STATE['certificate'], SSLSupportMethod='sni-only', MinimumProtocolVersion='TLSv1.2_2021')
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json') as output:
            json.dump(config, output); output.flush()
            aws('cloudfront', 'update-distribution', '--id', STATE['distribution'], '--if-match', distribution['ETag'], '--distribution-config', 'file://' + output.name)
    print('Submitted App-only update:', args.operation)


if __name__ == '__main__':
    main()
