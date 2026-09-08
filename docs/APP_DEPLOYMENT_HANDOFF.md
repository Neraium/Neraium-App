# Historical workbench deployment handoff

Checked September 8, 2026. The default frontend entry is `frontend/src/index.js`
→ `App.js`, mounted at `/`, with no router or connector imports. New evaluations
are paired reference/comparison. Legacy components remain outside that import
path. Internal analyst authentication is retained; it is not connector setup.

## Observed deployment gap

`https://app.neraium.com` returned HTTP 200 through Cloudflare/CloudFront and an
HTML shell loading `/assets/index-4Yff8wlr.js`. This repository uses CRA/CRACO,
which produces `/static/js/main.*.js`; the live artifact is therefore not the
current frontend build. This observation does not identify the origin owner or
prove which authenticated screens a user currently sees.

`.github/workflows/ci.yml` only runs checks. GitHub's deployments API returned
no deployments; Pages was not configured. No verified app.neraium.com publish
command, origin/distribution target, or safe deployment credentials configuration
was found in the inspected repo configuration. The legacy frontend Dockerfile
starts a development server with a localhost API; it is not a production path.
README explicitly limits the current backend to one local analyst, loopback and
one worker. Historical Docker/customer/live deployment documents do not apply.
No deployment, AWS operation, or credential inspection was performed.

## Exact next step

The deployment owner must first identify the pipeline and origin serving
app.neraium.com and supply a supported private workbench backend/access boundary.
The current local-only backend must not be exposed publicly as a shortcut.
After PR review and merge, that pipeline must build this repository's approved
revision, using its reachable workbench backend origin:

```bash
cd frontend
npm ci --ignore-scripts --no-audit --no-fund
REACT_APP_BACKEND_URL="$WORKBENCH_BACKEND_ORIGIN" CI=true npm run build
```

`WORKBENCH_BACKEND_ORIGIN` must be the verified backend origin (without `/api`),
not a token. Publish `frontend/build/` using the owner's verified hosting pipeline
and refresh cached HTML. An exact production publish command cannot be provided
until the hosting target and supported backend are identified; no safe command
exists here. Building alone does not switch the live site.

Then verify `/` shows Historical Evaluation, analyst access opens New Evaluation,
and a reference/comparison evaluation proceeds through compatibility, mapping,
authoritative SII, evidence review and report export without any connector entry
points. Check the same flow at a narrow mobile viewport. Until that deployment
and verification happen, the app.neraium.com success condition remains unmet.
