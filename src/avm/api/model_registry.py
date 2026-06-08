"""Model registry: load AVMModelBundle from S3 (or local) via latest.json pointer.

The registry caches the bundle as a module-level singleton and exposes
`get_bundle()` so that request handlers always use the current model without
holding the loaded artifact in each request.  Call `refresh()` to hot-swap
a newly published daily model without restarting the container.
"""

import logging
import os
import threading
from typing import Optional

from src.avm.io import storage
from src.avm.models.ensemble import AVMModelBundle

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_bundle: Optional[AVMModelBundle] = None
_latest_run_date: Optional[str] = None


def _resolve_latest_json() -> str:
    artifacts_bucket = os.environ.get("AVM_ARTIFACTS_BUCKET", "")
    if artifacts_bucket:
        return f"s3://{artifacts_bucket}/models/latest.json"
    return os.environ.get("AVM_LATEST_JSON", "models/latest.json")


def load() -> None:
    """Load (or reload) the model bundle pointed to by latest.json."""
    global _bundle, _latest_run_date
    latest_path = _resolve_latest_json()
    if not storage.exists(latest_path):
        raise FileNotFoundError(f"latest.json not found at {latest_path!r}")
    pointer = storage.read_json(latest_path)
    prefix = pointer["model_prefix"]
    logger.info("Loading bundle from %s", prefix)
    new_bundle = AVMModelBundle.load_bundle(prefix)
    with _lock:
        _bundle = new_bundle
        _latest_run_date = pointer.get("run_date")
    logger.info("Bundle loaded (run_date=%s)", _latest_run_date)


def get_bundle() -> AVMModelBundle:
    """Return the cached bundle; raises RuntimeError if not yet loaded."""
    with _lock:
        if _bundle is None:
            raise RuntimeError("Model bundle not loaded. Call load() first.")
        return _bundle


def get_run_date() -> Optional[str]:
    with _lock:
        return _latest_run_date


def is_ready() -> bool:
    with _lock:
        return _bundle is not None


def refresh() -> None:
    """Reload the bundle from latest.json (hot-swap on daily model publish)."""
    load()
