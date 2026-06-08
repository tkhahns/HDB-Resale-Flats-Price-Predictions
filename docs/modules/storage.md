# Storage (IO)

`src/avm/io/storage.py` — transparent local / S3 helpers backed by `fsspec`.

Set `AVM_ARTIFACTS_BUCKET` and/or `AVM_DATA_BUCKET` environment variables to route all
writes to S3.  Unset → all operations target the local filesystem.

| Function | Description |
|---|---|
| `makedirs(path)` | `mkdir -p` for local; no-op for `s3://` |
| `exists(path)` | `Path.exists` or `s3fs.exists` |
| `open_path(path, mode)` | Returns a `fsspec.open` context manager |
| `save_joblib(obj, path)` | `joblib.dump` via fsspec |
| `load_joblib(path)` | `joblib.load` via fsspec |
| `write_text(path, text)` | Write string to any path |
| `read_text(path)` | Read string from any path |
| `write_json(data, path)` | `json.dumps` → `write_text` |
| `read_json(path)` | `read_text` → `json.loads` |
| `savefig(fig_or_plt, path)` | Matplotlib figure via `BytesIO` buffer → fsspec write |
