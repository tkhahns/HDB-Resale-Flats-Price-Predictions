# ADR-003: Shared base Docker image

**Status:** Accepted

**Context:** Both the batch pipeline and the FastAPI service share the same Python
dependencies.  LightGBM and XGBoost both require `libgomp1` at runtime (not at build
time) — easy to miss.

**Decision:** Use a multi-stage build in `docker/Dockerfile.base`:
- Builder stage: `python:3.11` with compilers to install all wheels.
- Runtime stage: `python:3.11-slim` + `libgomp1` only.

`Dockerfile.batch` and `Dockerfile.api` set `ARG BASE_IMAGE` and `FROM ${BASE_IMAGE}`,
so the CI pipeline builds base once and reuses it for both images.

**Consequences:** Slightly more complex build pipeline (build base first, then derivatives)
but significantly smaller final images and guaranteed `libgomp1` presence.
