"""Shared constants for TheMinersFinder3000."""

DEFAULT_PORT = 25565
PROTOCOL_VERSION = 763
DEFAULT_CACHE = ".mcscan_cache.json"
CACHE_VERSION = 2

# Rows rendered per page (pagination keeps the table cheap regardless of list size).
PAGE_SIZE = 200
# How many entries are tested per refresh tick while computing the match count.
MATCH_CHUNK = 20000
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
