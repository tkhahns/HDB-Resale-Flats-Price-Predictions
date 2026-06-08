# ADR-004: latest.json model pointer

**Status:** Accepted

**Context:** Models are published daily to `s3://…/models/date=YYYY-MM-DD/`.  The API
needs to know which prefix to load without hardcoding dates.

**Decision:** The batch pipeline writes `s3://…/models/latest.json` as the very last step
on success, containing `{model_prefix, run_date, metrics}`.  The API reads this file
on startup and on `refresh()`.

**Why write it last?** If the pipeline crashes mid-run, `latest.json` still points to the
previous good model.  A partial bundle is never exposed to the API.

**Rollback procedure:** Overwrite `latest.json` to point to any prior `date=` prefix, then
force a new ECS deployment.  No code change or redeployment required.

**Consequences:** The API always serves the most recently successfully published model.
There is a window between batch completion and API hot-swap (one task restart cycle, ~60s).
