# Dedicated App production stack

Application source is the clean `main` revision
`ae7dadc35aee45f48a42b1bf60f62f98186669c4`. Authority remains
`6e26a83a17babaea443b75c545a756835d37102b`. Deployment files are a separate
hosting layer; no application or analytical source was edited.

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
  image/secret/log access; it does not grant public inbound access.
- API: explicit `REACT_APP_BACKEND_URL=.` resolves to same-origin `/api` at `/`.
  CloudFront forwards the workbench token, content type and query string; API
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
- Authentication: the existing tab-memory workbench token, injected from
  Secrets Manager `neraium-app-prod/workbench-token`. Retrieve the secret through
  an authorized Secrets Manager session; never put it in frontend configuration,
  Git, URLs or terminal transcripts. No static AWS credentials are used.
- Verification: public `/version.json`, backend `/healthz`, authenticated
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
```

For rollback, set the recorded image digest and task definition to a previously
verified App image, then use the same backend update. S3 object versions preserve
older frontend assets. Never use Demo or PPC resources for rollback.

Focused deployed checks create clearly named synthetic evaluations (no customer
data), preserve both uploads, verify authoritative evidence and export reports:

```bash
python3 deploy/production/verify.py https://d1gouhm82x409l.cloudfront.net --token-file /secure/path/token
# With a supported Node and playwright installation:
node deploy/production/browser-check.cjs /secure/path/token
```

## DNS handoff — no DNS changes made

The CloudFront hostname can be tested immediately. The App custom domain cannot
be attached until its certificate is issued. The ACM certificate is in
`us-east-1`, ARN recorded in `resources.json`.

1. Add the certificate-validation CNAME as **DNS only**:
   - Name: `_ea20d7b6bf9b504996b246869a2b7fe5.app.neraium.com`
   - Value: `_238a929a298790122d6d33f40888ebe3.jkddzztszm.acm-validations.aws`
2. After ACM status becomes `ISSUED`, attach the certificate and alias to the
   **new App distribution only**:
   `python3 deploy/production/deploy.py attach-domain`.
   Wait for CloudFront status `Deployed`. If an alias conflict is returned, stop;
   this command does not modify any other distribution.
3. Only after that, the domain owner can set the application CNAME:
   `app.neraium.com` → `d1gouhm82x409l.cloudfront.net` (DNS only for direct
   CloudFront delivery). This deployment does not call Cloudflare or change DNS.

Do not modify CloudFront `E3F7ZUIABOQRDX`,
`d2dk7dv2xhv65b.cloudfront.net`, `demo.neraium.com`,
`neraium-demo-preview-alb-origin`, or any PPC infrastructure/roles.
