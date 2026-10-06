"""Loading and saving the scan cache (JSON)."""

import json
from pathlib import Path

from .constants import CACHE_VERSION


def load_cache(path):
    """Load the cache file, returning a list of normalized entry dicts.

    Handles both the v2 ``{"version": 2, "servers": [...]}`` format and the
    legacy bare-list format. Raises on I/O or JSON errors.
    """
    path = Path(path)
    if not path.exists():
        return []
    data = json.loads(path.read_text())
    servers = data.get("servers", []) if isinstance(data, dict) else data
    out = []
    for r in servers:
        if not isinstance(r, dict) or "host" not in r:
            continue
        r.setdefault("state", "online")
        if r["state"] in ("scanning", "queued"):
            r["state"] = "queued"
        r.setdefault("starred", False)
        r.setdefault("whitelist", "unknown")
        out.append(r)
    return out


def dump_entries(entries):
    """Serialize entries to the cache payload (drops the transient ``_search``)."""
    return {
        "version": CACHE_VERSION,
        "servers": [{k: v for k, v in e.items() if k != "_search"} for e in entries],
    }


def save_cache(path, entries):
    Path(path).write_text(json.dumps(dump_entries(entries)))
