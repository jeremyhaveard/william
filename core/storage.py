"""
core/storage.py — Unified file storage for william.

Locally  : reads/writes under OUTPUT_DIR (output/ by default)
On AWS   : reads/writes to S3 when william_S3_BUCKET is set

Agents always use simple relative paths like "output/report.md" or just
"report.md" — this layer resolves where that actually lives.

Environment variables
  william_S3_BUCKET   S3 bucket name (activates S3 mode)
  william_S3_PREFIX   Key prefix inside the bucket (default: "william")
  william_OUTPUT_DIR  Local output directory (default: ./output)
"""

import io
import os
from pathlib import Path
from typing import Optional

# ── Config ───────────────────────────────────────────────────────
_S3_BUCKET  = os.getenv("william_S3_BUCKET", "")
_S3_PREFIX  = os.getenv("william_S3_PREFIX", "william").rstrip("/")
_OUTPUT_DIR = Path(os.getenv("william_OUTPUT_DIR",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")
)).resolve()

_USE_S3 = bool(_S3_BUCKET)

# Lazy S3 client — only created when needed
_s3_client = None


def _s3():
    global _s3_client
    if _s3_client is None:
        import boto3
        _s3_client = boto3.client("s3")
    return _s3_client


def _s3_key(path: str) -> str:
    """Convert a relative path to an S3 key under the configured prefix."""
    # Strip leading output/ so agents don't need to know about S3 layout
    clean = path.lstrip("/").removeprefix("output/")
    return f"{_S3_PREFIX}/{clean}"


def _local_path(path: str) -> Path:
    """Resolve a relative path to an absolute local path."""
    p = Path(path)
    if p.is_absolute():
        return p
    # Strip leading output/ if present — we root everything under OUTPUT_DIR
    parts = p.parts
    if parts and parts[0] == "output":
        p = Path(*parts[1:]) if len(parts) > 1 else Path("unnamed")
    return _OUTPUT_DIR / p


# ── Public API ───────────────────────────────────────────────────

def write_file(path: str, content: str | bytes, thread_id: Optional[str] = None) -> str:
    """
    Write content to storage.

    path       : relative path, e.g. "report.md" or "output/data.json"
    content    : text string or bytes
    thread_id  : if provided, files are namespaced under threads/{thread_id}/
    Returns    : a human-readable location string ("s3://..." or absolute path)
    """
    if thread_id:
        # Namespace under the thread so history stays organized
        bare = Path(path).name
        path = f"threads/{thread_id}/{bare}"

    if isinstance(content, str):
        data = content.encode("utf-8")
    else:
        data = content

    if _USE_S3:
        key = _s3_key(path)
        _s3().put_object(Bucket=_S3_BUCKET, Key=key, Body=data)
        location = f"s3://{_S3_BUCKET}/{key}"
    else:
        local = _local_path(path)
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_bytes(data)
        location = str(local)

    return location


def read_file(path: str, thread_id: Optional[str] = None) -> str:
    """
    Read a file from storage. Returns text content.
    Raises FileNotFoundError if the file doesn't exist.
    """
    if thread_id:
        bare = Path(path).name
        path = f"threads/{thread_id}/{bare}"

    if _USE_S3:
        key = _s3_key(path)
        try:
            resp = _s3().get_object(Bucket=_S3_BUCKET, Key=key)
            return resp["Body"].read().decode("utf-8")
        except _s3().exceptions.NoSuchKey:
            raise FileNotFoundError(f"s3://{_S3_BUCKET}/{key}")
    else:
        local = _local_path(path)
        if not local.exists():
            # Also try the raw path as given (absolute or relative to cwd)
            raw = Path(path)
            if raw.exists():
                return raw.read_text(encoding="utf-8")
            raise FileNotFoundError(str(local))
        return local.read_text(encoding="utf-8")


def read_file_bytes(path: str, thread_id: Optional[str] = None) -> bytes:
    """Read a file as raw bytes (for binary files like docx/xlsx/pptx)."""
    if thread_id:
        bare = Path(path).name
        path = f"threads/{thread_id}/{bare}"

    if _USE_S3:
        key = _s3_key(path)
        resp = _s3().get_object(Bucket=_S3_BUCKET, Key=key)
        return resp["Body"].read()
    else:
        return _local_path(path).read_bytes()


def write_file_bytes(path: str, data: bytes, thread_id: Optional[str] = None) -> str:
    """Write raw bytes to storage (for binary files like docx/xlsx/pptx)."""
    return write_file(path, data, thread_id=thread_id)


def list_files(prefix: str = "") -> list[str]:
    """
    List files under a prefix. Returns relative paths.
    """
    if _USE_S3:
        s3_prefix = _s3_key(prefix) if prefix else _S3_PREFIX + "/"
        resp = _s3().list_objects_v2(Bucket=_S3_BUCKET, Prefix=s3_prefix)
        return [
            obj["Key"].removeprefix(_S3_PREFIX + "/")
            for obj in resp.get("Contents", [])
        ]
    else:
        root = _local_path(prefix) if prefix else _OUTPUT_DIR
        if not root.exists():
            return []
        return [
            str(p.relative_to(_OUTPUT_DIR))
            for p in root.rglob("*")
            if p.is_file()
        ]


def file_url(path: str, thread_id: Optional[str] = None) -> str:
    """Return a human-readable location string for a stored file."""
    if thread_id:
        bare = Path(path).name
        path = f"threads/{thread_id}/{bare}"
    if _USE_S3:
        return f"s3://{_S3_BUCKET}/{_s3_key(path)}"
    return str(_local_path(path))


def using_s3() -> bool:
    """Returns True when S3 mode is active."""
    return _USE_S3
