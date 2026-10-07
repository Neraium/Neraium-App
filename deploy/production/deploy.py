"""Update only the recorded App stack. Never changes DNS or other distributions."""
import argparse
import json
from pathlib import Path
import re
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
    parser.add_argument('operation', choices=['frontend', 'backend', 'remove-token-forwarding', 'attach-domain'])
    parser.add_argument('--build', type=Path)
    args = parser.parse_args()
    if args.operation == 'frontend':
        if not args.build or not args.build.is_dir():
            raise SystemExit('Supply --build /path/to/frontend/build')
        version = json.loads((args.build / 'version.json').read_text())
        if (version.get('commit') != STATE['application_commit']
                or version.get('authority_commit') != STATE['authority_commit']):
            raise SystemExit('Frontend version must match both current release commits.')
    elif args.operation == 'backend':
        digest = STATE.get('image_digest')
        if not isinstance(digest, str) or not re.fullmatch(r'sha256:[0-9a-f]{64}', digest):
            raise SystemExit('Current release image digest is unset. Build and verify the pinned release before recording its published digest.')
        definition = json.loads((HERE / 'task-definition.json').read_text())
        if definition['containerDefinitions'][0]['image'] != STATE['ecr_repository'] + '@' + digest:
            raise SystemExit('Task image must match the current release image digest.')
    assert aws('sts', 'get-caller-identity')['Account'] == STATE['account']
    assert STATE['distribution'] == 'E27KJ5Y66YQQBO'
    distribution = aws('cloudfront', 'get-distribution-config', '--id', STATE['distribution'])
    config = distribution['DistributionConfig']
    assert config['Comment'].startswith('Neraium-App dedicated production;')
    assert {o['Id'] for o in config['Origins']['Items']} == {'app-frontend', 'app-api'}

    if args.operation == 'frontend':
        subprocess.run(['aws', 's3', 'sync', str(args.build), 's3://' + STATE['frontend_bucket'] + '/', '--region', STATE['region'], '--exclude', '*.map', '--cache-control', 'no-cache', '--only-show-errors'], check=True)
        aws('cloudfront', 'create-invalidation', '--distribution-id', STATE['distribution'], '--paths', '/*')
    elif args.operation == 'backend':
        assert definition['family'] == 'neraium-app-prod'
        assert definition['containerDefinitions'][0]['image'] == STATE['ecr_repository'] + '@' + STATE['image_digest']
        registered = aws('ecs', 'register-task-definition', document=definition)['taskDefinition']['taskDefinitionArn']
        aws('ecs', 'update-service', '--cluster', STATE['cluster'], '--service', 'neraium-app-prod', '--task-definition', registered)
        STATE['task_definition'] = registered
        (HERE / 'resources.json').write_text(json.dumps(STATE, indent=2) + '\n')
    elif args.operation == 'remove-token-forwarding':
        for behavior in config['CacheBehaviors']['Items']:
            headers = behavior.get('ForwardedValues', {}).get('Headers', {})
            if 'X-Workbench-Token' in headers.get('Items', []):
                assert behavior['TargetOriginId'] == 'app-api'
                headers['Items'].remove('X-Workbench-Token')
                headers['Quantity'] = len(headers['Items'])
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json') as output:
            json.dump(config, output); output.flush()
            aws('cloudfront', 'update-distribution', '--id', STATE['distribution'], '--if-match', distribution['ETag'], '--distribution-config', 'file://' + output.name)
    else:
        certificate = aws('acm', 'describe-certificate', '--certificate-arn', STATE['certificate'])['Certificate']
        assert certificate['Status'] == 'ISSUED', 'Certificate DNS validation must complete first. No DNS changes were made.'
        assert 'eval.neraium.com' in certificate['SubjectAlternativeNames']
        config['Aliases'] = dict(Quantity=1, Items=['eval.neraium.com'])
        config['ViewerCertificate'] = dict(ACMCertificateArn=STATE['certificate'], SSLSupportMethod='sni-only', MinimumProtocolVersion='TLSv1.2_2021')
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json') as output:
            json.dump(config, output); output.flush()
            aws('cloudfront', 'update-distribution', '--id', STATE['distribution'], '--if-match', distribution['ETag'], '--distribution-config', 'file://' + output.name)
    print('Submitted App-only update:', args.operation)


if __name__ == '__main__':
    main()
