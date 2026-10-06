"""Rich markup helpers used by the UI."""


def latency_style(ms):
    """Color for a latency value in milliseconds."""
    if ms < 80:
        return "#22c55e"
    if ms < 200:
        return "#eab308"
    return "#ef4444"


def player_bar(online, mx):
    """A small ``████░░ 42/100`` style bar."""
    if not mx:
        return f"[#6b7280]{online}/?[/]"
    frac = max(0.0, min(1.0, online / mx))
    filled = round(frac * 12)
    color = "#22c55e" if frac >= 0.8 else "#eab308" if frac >= 0.4 else "#06b6d4"
    return f"[{color}]{'█' * filled}[/][#242038]{'░' * (12 - filled)}[/] [#e5e7eb]{online}/{mx}[/]"
