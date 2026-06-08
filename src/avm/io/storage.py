"""Transparent local / S3 storage helpers (fsspec-backed).

All modules in this project route filesystem operations through this module so
that ``s3://`` and local paths are interchangeable with zero config changes — just
set ``AVM_ARTIFACTS_BUCKET`` / ``AVM_DATA_BUCKET`` env vars and every read/write
transparently targets S3.

Supported operations:
    makedirs   no-op for s3://, mkdir -p for local paths
    exists     Path.exists or s3fs.exists
    open_path  fsspec.open context manager
    save_joblib / load_joblib   joblib through fsspec
    write_text / read_text      text files through fsspec
    write_json / read_json      JSON helpers
    savefig                     matplotlib figure to any path
"""

import io
import json
import logging
from pathlib import Path
from typing import Any

import fsspec
import joblib

logger = logging.getLogger(__name__)


def _is_s3(path: str) -> bool:
    return str(path).startswith("s3://")


# ---------------------------------------------------------------------------
# Directory helpers
# ---------------------------------------------------------------------------

def makedirs(path: str) -> None:
    """Create parent directories. No-op for s3:// (object-store flat namespace)."""
    if not _is_s3(path):
        p = Path(path)
        # If path looks like a directory (no suffix or ends with /) use it directly
        if str(path).endswith("/") or not p.suffix:
            p.mkdir(parents=True, exist_ok=True)
        else:
            p.parent.mkdir(parents=True, exist_ok=True)


def exists(path: str) -> bool:
    """Return True if the path exists (local file or S3 object)."""
    if _is_s3(path):
        import s3fs
        fs = s3fs.S3FileSystem(anon=False)
        return fs.exists(path)
    return Path(path).exists()


# ---------------------------------------------------------------------------
# Generic open
# ---------------------------------------------------------------------------

def open_path(path: str, mode: str = "rb"):
    """Return a fsspec open context manager for local or S3 paths."""
    return fsspec.open(path, mode)


# ---------------------------------------------------------------------------
# joblib
# ---------------------------------------------------------------------------

def save_joblib(obj: Any, path: str) -> None:
    makedirs(path)
    with fsspec.open(path, "wb") as f:
        joblib.dump(obj, f)
    logger.debug("save_joblib → %s", path)


def load_joblib(path: str) -> Any:
    with fsspec.open(path, "rb") as f:
        return joblib.load(f)


# ---------------------------------------------------------------------------
# Text / JSON
# ---------------------------------------------------------------------------

def write_text(path: str, text: str) -> None:
    makedirs(path)
    with fsspec.open(path, "w") as f:
        f.write(text)


def read_text(path: str) -> str:
    with fsspec.open(path, "r") as f:
        return f.read()


def write_json(data: dict, path: str) -> None:
    write_text(path, json.dumps(data, indent=2, default=str))


def read_json(path: str) -> dict:
    return json.loads(read_text(path))


# ---------------------------------------------------------------------------
# Matplotlib
# ---------------------------------------------------------------------------

def savefig(fig_or_plt: Any, path: str, **kwargs) -> None:
    """Save a matplotlib Figure or the pyplot module to any fsspec path."""
    makedirs(path)
    kwargs.setdefault("dpi", 150)
    buf = io.BytesIO()
    fig_or_plt.savefig(buf, **kwargs)
    buf.seek(0)
    with fsspec.open(path, "wb") as f:
        f.write(buf.read())
    logger.debug("savefig → %s", path)
