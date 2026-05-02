"""Log source resolution for execution log references."""
from __future__ import annotations

import base64


async def fetch_log(log_ref: str) -> str | None:
    """Resolve a log_ref string and return its text content.

    Supported schemes:
      inline:<base64>   — base64-encoded log text stored directly in log_ref
      file://<path>     — read from local filesystem asynchronously

    Returns None if the source exists but has no content (e.g. missing file).
    Returns an error string for unknown schemes rather than raising.
    """
    if log_ref.startswith("inline:"):
        encoded = log_ref[len("inline:"):]
        return base64.b64decode(encoded).decode("utf-8", errors="replace")

    if log_ref.startswith("file://"):
        import aiofiles

        path = log_ref[len("file://"):]
        try:
            async with aiofiles.open(path) as fh:
                return await fh.read()
        except (FileNotFoundError, OSError):
            return None

    scheme = log_ref.split(":")[0] if ":" in log_ref else log_ref
    return f"<log source not supported: {scheme}>"
