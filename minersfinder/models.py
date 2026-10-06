"""Data model for a scanned server."""


def new_entry(host):
    """Create a blank (``queued``) entry for *host*."""
    return {
        "host": host, "state": "queued", "version": "", "online": 0, "max": 0,
        "motd_raw": "", "motd_clean": "", "latency": None, "players_sample": [],
        "mods": [], "whitelist": "unknown", "starred": False, "error": None,
        "_search": host.lower(),
    }


def search_blob(entry):
    """Text blob used for free-text filtering."""
    return " ".join([
        str(entry.get("host", "")), str(entry.get("version", "")),
        str(entry.get("motd_clean", "")), " ".join(entry.get("mods") or []),
    ]).lower()
