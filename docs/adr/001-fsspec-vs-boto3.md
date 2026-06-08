# ADR-001: fsspec vs boto3 for storage abstraction

**Status:** Accepted

**Context:** We need to read/write files from both local disk (dev) and S3 (prod) without
changing application code.

**Decision:** Use `fsspec` + `s3fs` via a thin `src/avm/io/storage.py` shim.
All filesystem operations (`makedirs`, `exists`, `open_path`, `save_joblib`, `savefig`,
`write_text`) route through this module.  The switch from local to S3 requires only setting
`AVM_ARTIFACTS_BUCKET` / `AVM_DATA_BUCKET` environment variables — no code changes.

**Alternatives considered:**

- **boto3 directly** — would require two code paths everywhere (local vs S3), making tests
  harder and dev experience worse.
- **s3fs directly** — fsspec wraps s3fs and adds unified `open()` semantics; same amount
  of code but more portable.

**Consequences:** `fsspec` and `s3fs` are runtime dependencies.  Local paths use
`pathlib`/stdlib; S3 paths use `s3fs.S3FileSystem`.
