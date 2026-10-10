"""Small OS helpers."""

import os
import re
import subprocess


def version_sort_key(version: str):
    """Sort key for a Minecraft version string.

    Extracts numeric groups so ``1.9`` sorts before ``1.20`` (and names like
    ``"Paper 1.20.1"`` order sensibly). A string with no digits sorts first.
    """
    return tuple(int(n) for n in re.findall(r"\d+", version or ""))


def copy_to_clipboard(text: str):
    """Copy *text* to the system clipboard (Wayland or X11), ignoring failures."""
    try:
        if os.environ.get("WAYLAND_DISPLAY"):
            subprocess.run(["wl-copy"], input=text.encode(), check=False)
        else:
            subprocess.run(["xclip", "-selection", "clipboard"], input=text.encode(), check=False)
    except Exception:
        pass
