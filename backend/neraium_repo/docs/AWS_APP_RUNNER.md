# AWS App Runner source-repository deployment (FastAPI)

This guide deploys Neraium from GitHub to AWS App Runner using the repository config file (`apprunner.yaml`) at repo root.

## Readiness audit summary

- **Source directory assumption:** deploy from repository root (`/`) because `apprunner.yaml` and `pyproject.toml` are at root.
- **Dependency installation path:** runtime `pre-run` install via `pip3 install .` (reads canonical dependencies from `pyproject.toml`) to ensure packages are available in App Runner Python 3.11 runtime.
- **FastAPI entrypoint:** `apps.api.main:app`.
- **Static assets:** served from `apps/api/static` through router + `/web` static mount.
- **Health endpoint:** `GET /health` returns JSON `200`.
- **Requirements layout:** root `requirements.txt` is a compatibility shim that delegates to `pyproject.toml` via `.` install.
- **Platform scope:** AWS App Runner (Railway is intentionally not part of the deployment path for this repo).

## App Runner console steps (source code repository)

1. Open **AWS App Runner** → **Create service**.
2. Choose **Source code repository**.
3. Connect/select your GitHub repository.
4. Set **Branch** to your deployment branch (for example `main`).
5. Set **Source directory** to `/` (repository root).
6. In **Deployment settings / Configuration**, choose to use the repository configuration file (`apprunner.yaml`).
7. Create/deploy service.

## App paths after deploy

- API docs (if enabled): `/docs`
- Health: `/health`
- Primary operational UI: `/dashboard` (also `/pilot`, `/operations`)
- Operator compatibility routes: `/operator`, `/operator/workflow` (redirect to `/dashboard`)
- Historical replay routes: `/demo`, `/demo/full` (redirect with replay mode enabled)
- Web static files mount: `/web/*`

## Why GitHub pushes may not update App Runner

If your App Runner service is connected to GitHub but new commits do **not** deploy,
it is usually one of these operational issues (outside app code):

1. **Automatic deployment is disabled** in the App Runner service settings.
2. **Branch mismatch**: App Runner watches one branch, while changes land in another.
3. **Stale GitHub connection/webhook**: App Runner can lose webhook delivery after
   repo/org permission changes or GitHub App authorization updates.

A practical hardening step is to trigger deployments from GitHub Actions on each
push to `main`.

### Included fallback workflow (recommended)

This repository now includes `.github/workflows/aws-apprunner-redeploy.yml`.
On every push to `main` (or manual dispatch), it calls:

- `aws apprunner start-deployment --service-arn <your-service-arn>`

That forces App Runner to pull the latest watched branch commit even if webhook
notifications were missed.

### Required GitHub configuration

Set these in your GitHub repo before enabling the workflow:

- **Repository variable:** `AWS_REGION` (for example `us-east-1`)
- **Repository variable:** `AWS_APP_RUNNER_SERVICE_ARN`
- **Repository secret:** `AWS_GITHUB_DEPLOY_ROLE_ARN` (IAM role trusted by GitHub OIDC)

IAM role needs at minimum:

- `apprunner:StartDeployment` on the target service ARN.

## Common failure points

1. **Wrong source directory**
   - Symptom: App Runner ignores `apprunner.yaml` or cannot find dependencies.
   - Fix: ensure source directory is `/`.

2. **Config file name mismatch**
   - Symptom: App Runner uses console defaults instead of repo-defined commands.
   - Fix: file must be exactly `apprunner.yaml` (not `.yml`).

3. **Dependency install omitted for Python 3.11 pre-run flow**
   - Symptom: startup fails with import errors.
   - Fix: keep the explicit `pip3 install .` command in `run.pre-run` of `apprunner.yaml`.

4. **Wrong app command**
   - Symptom: service starts but immediately exits or returns 502.
   - Fix: use `python3 -m uvicorn apps.api.main:app --host 0.0.0.0 --port 8000 --proxy-headers`.
   - If logs show `exec: "uvicorn": executable file not found in $PATH`, this module form avoids PATH issues.

5. **Static web asset issues**
   - Symptom: `/dashboard` (or `/operator` redirect) 404 or missing JS/CSS.
   - Fix: confirm `apps/api/static/*` exists in the deployed branch and source directory is root.

## Fast checklist when "the website still shows the old version"

Use this order to isolate where the stale version is coming from:

1. **Confirm the live service is your latest commit**
   - In App Runner, open your service **Deployments** tab and verify the latest
     deployment references the same Git commit you just pushed.
   - If it does not, run **Deploy** (or call `StartDeployment`) to force a pull.

2. **Verify branch and source directory**
   - Ensure App Runner is watching the branch you actually updated.
   - Ensure source directory is `/` so `apprunner.yaml` and static assets are used.

3. **Check you are opening the correct domain**
   - Confirm you are using the current App Runner default URL or your active custom
     domain, not an old environment URL.
   - If both `www` and apex are configured, verify which one your DNS points to.

4. **Bypass browser cache / service worker**
   - Hard refresh (`Ctrl+Shift+R` on Windows/Linux, `Cmd+Shift+R` on macOS).
   - Open an incognito/private window.
   - In browser devtools → Application, unregister any old service worker and clear
     site data for the domain if stale assets persist.

5. **Validate static asset freshness directly**
   - Open a JS asset URL directly (for example `/web/modules/boot.js`) and confirm
     the response contains your latest changes.
   - If this file is old, the issue is deployment/source branch; if this file is new
     but UI is old, the issue is browser cache or service worker.

## If App Runner keeps saying "rollback succeeded"

That message means the **new deployment failed health/startup checks**, so App Runner
restored the previous healthy version. Your latest code is not live yet.

Use this quick recovery sequence:

1. **Open failed deployment logs first**
   - App Runner service → **Deployments** → open the failed deployment → inspect
     application/startup logs.
   - Look for import errors, missing env vars, bad startup command, or 5xx on boot.

2. **Verify runtime command and port**
   - Ensure the command is still:
     `python3 -m uvicorn apps.api.main:app --host 0.0.0.0 --port 8000 --proxy-headers`
   - App Runner expects the app to bind successfully and respond healthy.

3. **Confirm required environment variables are present**
   - Missing env vars can cause startup exceptions and immediate rollback.
   - Recheck any recent variable renames in App Runner service configuration.

4. **Test locally with production-like startup**
   - From repository root:
     `pip3 install .`
     `python3 -m uvicorn apps.api.main:app --host 0.0.0.0 --port 8000 --proxy-headers`
   - Confirm `GET /health` returns `200` before redeploying.

5. **Trigger a fresh deployment after fixing root cause**
   - Redeploy from App Runner console or run `StartDeployment`.
   - Then re-check the deployment commit SHA and `/health`.

If rollback repeats with no clear app error, validate that your service instance role
and network settings still allow required startup dependencies (for example secrets,
datastores, or private endpoints).

## 10-minute step-by-step recovery playbook

If you just want exact steps to follow, do this in order:

1. **Get the failing reason in AWS**
   - App Runner → your service → **Deployments** → open latest failed deploy.
   - Copy the first startup error line from application logs.

2. **Fix configuration drift**
   - Confirm service is watching the correct branch.
   - Confirm source directory is `/`.
   - Confirm runtime command is:
     `python3 -m uvicorn apps.api.main:app --host 0.0.0.0 --port 8000 --proxy-headers`

3. **Re-check environment variables**
   - Compare App Runner env vars with what your latest code expects.
   - Re-add any missing keys and save.

4. **Verify app health locally**
   - Run:
     `pip3 install .`
     `python3 -m uvicorn apps.api.main:app --host 0.0.0.0 --port 8000 --proxy-headers`
   - Open `http://127.0.0.1:8000/health` and confirm `200`.

5. **Force a fresh deploy**
   - In App Runner click **Deploy**, or run:
     `aws apprunner start-deployment --service-arn <YOUR_SERVICE_ARN> --region <AWS_REGION>`

6. **Confirm new version is actually live**
   - In Deployments, confirm latest deployment is **Operation succeeded**.
   - Open `https://<your-domain>/health`.
   - Open `https://<your-domain>/web/modules/boot.js` and verify your latest change appears.

7. **If browser still looks old**
   - Hard refresh (`Ctrl/Cmd + Shift + R`), then open an incognito window.
   - Clear site data / unregister service worker for your domain.

## If you resolved a merge conflict incorrectly

If you picked the wrong side during conflict resolution (for example `apprunner.yaml`),
restore the known-good deployment files and redeploy.

```bash
# 1) Inspect current versions
git status
git diff -- apprunner.yaml docs/AWS_APP_RUNNER.md

# 2) Restore from the latest good commit (replace with your known-good SHA)
# Find candidate SHAs that last changed these files:
git log --oneline -- apprunner.yaml docs/AWS_APP_RUNNER.md

# Optional: inspect a candidate before restoring
git show <GOOD_SHA> -- apprunner.yaml docs/AWS_APP_RUNNER.md

# Restore from the chosen good SHA
git checkout <GOOD_SHA> -- apprunner.yaml docs/AWS_APP_RUNNER.md

# 3) Commit and push
git add apprunner.yaml docs/AWS_APP_RUNNER.md
git commit -m "fix: restore App Runner deployment config after bad conflict resolution"
git push
```

Then trigger App Runner deployment and verify `/health`.
## Railway decommissioning note

This repository is intentionally configured for AWS deployment workflows only.
If a historical Railway service exists, treat it as decommissioned and keep Railway
GitHub integration disabled to prevent accidental redeploys.
