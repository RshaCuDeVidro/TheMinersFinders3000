"""Query language for filtering scanned servers.

Space-separated terms are combined with AND. A bare term is a free-text
substring match; ``key:value`` applies a field filter::

    mod:create  ver:1.20  host:mc.  players:>20  ping:<50
    wl:yes  state:failed  starred:1
"""


def _num_cmp(value, expr):
    op = "="
    for o in (">=", "<=", ">", "<", "="):
        if expr.startswith(o):
            op, expr = o, expr[len(o):]
            break
    try:
        n = float(expr)
    except ValueError:
        return False
    if op == ">":
        return value > n
    if op == "<":
        return value < n
    if op == ">=":
        return value >= n
    if op == "<=":
        return value <= n
    return value == n


def _term(entry, key, val):
    if key == "host":
        return val in entry.get("host", "").lower()
    if key in ("ver", "version"):
        return val in entry.get("version", "").lower()
    if key in ("mod", "mods", "modid"):
        return any(val in m.lower() for m in (entry.get("mods") or []))
    if key in ("wl", "whitelist"):
        table = {"y": "yes", "yes": "yes", "n": "no", "no": "no", "?": "unknown", "unknown": "unknown"}
        return entry.get("whitelist", "unknown") == table.get(val, val)
    if key in ("state", "status"):
        return entry.get("state", "") == val
    if key in ("star", "starred"):
        return bool(entry.get("starred")) == (val in ("1", "true", "yes", "y"))
    if key in ("players", "ply"):
        return _num_cmp(float(entry.get("online", 0) or 0), val)
    if key in ("ping", "latency", "ms"):
        lat = entry.get("latency")
        return lat is not None and _num_cmp(float(lat), val)
    return val in entry.get("_search", "")


def parse_query(text):
    """Compile *text* into a predicate ``f(entry) -> bool``."""
    free, preds = [], []
    for tok in text.lower().split():
        if ":" in tok:
            k, v = tok.split(":", 1)
            preds.append((k, v))
        elif tok:
            free.append(tok)

    def pred(entry):
        s = entry.get("_search", "")
        if any(f not in s for f in free):
            return False
        return all(_term(entry, k, v) for k, v in preds)

    return pred
