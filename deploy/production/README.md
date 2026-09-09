# Dedicated App production stack

The deployed application revision and immutable image digest are recorded in
`resources.json`. Authority remains pinned to
`6e26a83a17babaea443b75c545a756835d37102b`.

The new distribution is **E27KJ5Y66YQQBO**, at
**https://d1gouhm82x409l.cloudfront.net/**. `resources.json` records its dedicated
resources and exact image digest. The default VPC/subnets supply networking;
all App load balancing, security groups, compute, roles, ECR, storage and
frontend resources are dedicated to this stack. No Demo/PPC origins, buckets,
load balancers, application roles or APIs are used.

- Frontend: versioned, AES256-encrypted private S3, public access blocked,
  bucket-owner-enforced ownership, OAC restricted to the new distribution.
- Backend: CloudFront VPC origin → internal ALB → one Fargate task, one Uvicorn
  worker. Task ingress permits only the App ALB. The ALB permits only the AWS
  CloudFront VPC-origin service security group. A task public IP supplies outbound
  image/log access; it does not grant public inbound access.
- API: explicit `REACT_APP_BACKEND_URL=.` resolves to same-origin `/api` at `/`.
  CloudFront forwards content type and query string; API
  caching is disabled. ALB idle timeout is 150 seconds; CloudFront origin read
  timeout is 120 seconds, matching the existing analysis limit.
- Storage: encrypted EFS, TLS and IAM mount authorization, dedicated access
  point with UID/GID 10001 and mode 0700; network access only from the App task.
  Automatic EFS backup is enabled. SQLite stays in rollback-journal mode.
  `runtime.py` serializes complete API requests and holds a lifetime file lock;
  service replacement stops the old task before starting the new task.
  **Keep desiredCount=1, maximumPercent=100 and minimumHealthyPercent=0.**
  This remains a single-operator workbench, with brief downtime during updates.
- The root filesystem is read-only. `TMPDIR=/data` uses the encrypted writable
  mount for authority scratch directories, removed by the existing adapter.
- Access: Historical Evaluation opens directly without authentication. Only the
  workbench API and health/version metadata are mounted; legacy routes remain absent.
- Verification: public `/version.json`, backend `/healthz`, public
  `/api/version`, immutable ECR digest and `frontend-sha256.json` identify the
  deployed artifacts. Logs have 30-day retention and API access logging is off.

## Build and update

Build from the recorded Git revisions, not the working tree:

```bash
python3 deploy/production/build.py /tmp/neraium-app-production-build
```

The build uses Python 3.11 and Node 22, runs the focused UI/workbench tests and
includes the tiny real-authority integration tests. It excludes the large
8,640-row external contract check. Base tags/dependency ranges are resolved at
build time; the existing production release is reproducible by its immutable
image digest and recorded frontend hashes. Rebuilds must be revalidated before
updating the recorded digest. ECR tags are immutable.

`task-definition.json`, `service.json`, `cloudfront.json` and `bucket-policy.json`
are AWS CLI input documents. `cloudfront.json` is the initial creation config
without a custom-domain alias. `resources.json` is the existing-stack inventory,
not a fresh-stack provisioner. Do not replay create calls against existing names.
`deploy.py` updates only the recorded App stack and stops on any AWS error:

```bash
python3 deploy/production/deploy.py frontend --build /tmp/neraium-app-production-build/app/frontend/build
python3 deploy/production/deploy.py backend
python3 deploy/production/deploy.py remove-token-forwarding
```

For rollback, set the recorded image digest and task definition to a previously
verified App image, then use the same backend update. S3 object versions preserve
older frontend assets. Never use Demo or PPC resources for rollback.

Focused deployed checks create clearly named synthetic evaluations (no customer
data), preserve both uploads, verify authoritative evidence and export reports:

```bash
python3 deploy/production/verify.py https://eval.neraium.com
# With a supported Node and playwright installation:
node deploy/production/browser-check.cjs https://eval.neraium.com
```

## DNS handoff — no DNS changes made

The production hostname is `eval.neraium.com`. Its ACM certificate is issued in
`us-east-1`, with the ARN recorded in `resources.json`. The certificate and alias
are attached to `E27KJ5Y66YQQBO`, status `Deployed`. HTTPS verification using
`eval.neraium.com` with a direct CloudFront connection passed: frontend HTTP 200,
`/healthz` status `ok`, and `/version.json` confirmed the application and authority
commits above. Cloudflare traffic DNS remains unchanged. Retain the validation CNAME for certificate renewal.

1. Add the certificate-validation CNAME as **DNS only**:
   - Name: `_a2deca0bfd36a8c50b92f6da7a3e41fc.eval.neraium.com`
   - Value: `_7c3da83b0a841da84e1d0d702c178693.jkddzztszm.acm-validations.aws`
2. After ACM status becomes `ISSUED`, attach the certificate and alias to the
   **new App distribution only**:
   `python3 deploy/production/deploy.py attach-domain`.
   Wait for CloudFront status `Deployed`. If an alias conflict is returned, stop;
   this command does not modify any other distribution.
3. Only after that, the domain owner can set the application CNAME:
   `eval.neraium.com` → `d1gouhm82x409l.cloudfront.net` (DNS only for direct
   CloudFront delivery). This deployment does not call Cloudflare or change DNS.

Do not modify CloudFront `E3F7ZUIABOQRDX`,
`d2dk7dv2xhv65b.cloudfront.net`, `demo.neraium.com`,
`neraium-demo-preview-alb-origin`, or any PPC infrastructure/roles.

## Token-free release verification

The 2026-09-09 release opens `https://eval.neraium.com` directly in Historical
Evaluation. `verification.json` records the live API and desktop/mobile browser
checks, including reload without a prompt, paired intake/analysis, evidence and
report downloads, unchanged authority pin, and preservation of previous synthetic
uploads. Frontend returned HTTP 200; backend health and ALB target were healthy;
ECS completed with one running task. Retired product routes returned 404.

Only App frontend objects/invalidation, its backend image/task/service, and the
App distribution's token-header forwarding changed in AWS. The task no longer
injects a workbench secret. No secret value was retrieved, and existing Secrets
Manager/IAM resources were left untouched. Demo's distribution configuration and
ETag were unchanged; no PPC resources or DNS were modified.

The application source snapshot is retained locally as tag
`app-prod-tokenless-20260909` (`c9acadad1c48bba9f5d955253b0c5fdcb68fbb8b`).
Recovery confirmed that the current application and runtime source match that
already deployed snapshot exactly. The recovery commit records the completed
changes and refreshed verification; production version metadata continues to
identify the original immutable application snapshot. Focused tests passed
(38 backend, 3 frontend), and a fresh frontend build matched the deployed hashes.
