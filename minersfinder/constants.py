"""Shared constants for TheMinersFinder3000."""

DEFAULT_PORT = 25565
PROTOCOL_VERSION = 763
DEFAULT_CACHE = ".mcscan_cache.json"
CACHE_VERSION = 2

MAX_PLACEHOLDER_ROWS = 3000
MAX_DISPLAY_ROWS = 3000
DIRTY_BATCH = 250
REFRESH_INTERVAL = 0.5
AUTOSAVE_INTERVAL = 20.0

WL_KEYWORDS = (
    "whitelist", "white-list", "allowlist", "allowed list",
    "not invited", "not on the list", "not whitelisted",
    "listada", "lista de permitidos", "não está na lista", "nao esta na lista",
)

STATE_STYLE = {
    "queued": ("…", "#6b7280"),
    "scanning": ("⟳", "#06b6d4"),
    "online": ("●", "#22c55e"),
    "failed": ("✖", "#ef4444"),
}
