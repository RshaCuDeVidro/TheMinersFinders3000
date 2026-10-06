"""Small OS helpers."""

import os
import subprocess


def copy_to_clipboard(text: str):
    """Copy *text* to the system clipboard (Wayland or X11), ignoring failures."""
    try:
        if os.environ.get("WAYLAND_DISPLAY"):
            subprocess.run(["wl-copy"], input=text.encode(), check=False)
        else:
            subprocess.run(["xclip", "-selection", "clipboard"], input=text.encode(), check=False)
    except Exception:
        pass
