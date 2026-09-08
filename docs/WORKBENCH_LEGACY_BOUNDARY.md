# Retained legacy boundary

The initial inventory is in HISTORICAL_WORKBENCH_AUDIT.md. That document records
the pre-conversion state, not the current runtime. This inventory records the
conversion disposition; it does not claim all old files are individually audited.

| Legacy area | Status after conversion |
|---|---|
| `backend/routers/`, `backend/services/` | Retained as historical source. No routers mounted, no imports from `backend/workbench`, not installed with the workbench package. |
| `neraium_core/` | Retained old independent unified/advanced/local engines, hazard/RUL/validation and research implementations. Not installed or called by the workbench. |
| Old frontend components, `sii.js`, PRONOSTIA/narration helpers | Retained, outside the new App import graph. No live sockets, fake playback or local regime synthesis in the active bundle. |
| `tools/`, validation scripts, `results/`, `data/`, `fixtures/`, `memory/` | Legacy examples/research/output. Never treated as customer evidence, installed, or automatically run. No bulk deletion or datasets executed. |
| Root README / ARCHITECTURE | Replaced with accurate internal-workbench purpose and authority boundary. |
| `docs/GROW*`, old ingestion/deployment/proof/demo docs | Historical descriptions; README/ARCHITECTURE supersede them for this tool. Several reference absent files. |
| `launch.py`, `start.sh`, `start.bat` | Now launch the internal workbench on loopback without auto-installation or rewriting environment files. |
| Old Compose | Removed: obsolete Mongo/demo wiring and embedded credential. The previously committed credential requires owner rotation outside this PR. |
| Dockerfiles, `docker/`, old deployment configuration | Retained unsupported historical configuration; not the launch or deployment path. No container/cloud validation performed. |
| Benchmark/hero-plot CI | Removed because entrypoints were absent and execution is unrelated to the workbench. |
| Main CI | Focused workbench contracts and frontend build. External authority integration is opt-in, requiring the private pinned checkout. |

No old intelligence implementation was blindly deleted. Disconnection and package
exclusion establish the active boundary; later archival/removal can follow
separate reference audits. No Neraium-1.0 or Demo-Neraium source was changed.
