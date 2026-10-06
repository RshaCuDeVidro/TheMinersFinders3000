"""Minecraft legacy chat/MOTD formatting code parsing.

Handles the classic ``§`` color codes, the modern ``§x§R§R§G§G§B§B`` hex
sequence, uppercase codes and the obfuscated ``§k`` code.
"""

from rich.markup import escape

mc_colors = {
    '0': 'black', '1': 'dark_blue', '2': 'dark_green', '3': 'dark_cyan',
    '4': 'dark_red', '5': 'purple', '6': 'orange3', '7': 'grey70',
    '8': 'grey37', '9': 'blue', 'a': 'green', 'b': 'cyan',
    'c': 'red', 'd': 'pink1', 'e': 'yellow', 'f': 'white',
    'l': 'bold', 'm': 'strike', 'n': 'underline', 'o': 'italic', 'r': 'reset',
}


def _mc_tokens(text):
    """Split *text* into ``("text"|"color"|"style"|"hex"|"reset"|"skip", value)`` tokens."""
    tokens = []
    buf = []

    def flush():
        if buf:
            tokens.append(("text", "".join(buf)))
            del buf[:]

    i, n = 0, len(text)
    while i < n:
        if text[i] == '§' and i + 1 < n:
            code = text[i + 1].lower()
            if code == 'x' and i + 2 + 12 <= n:
                pairs = []
                j = i + 2
                for _ in range(6):
                    if j + 1 < n and text[j] == '§' and text[j + 1].lower() in "0123456789abcdef":
                        pairs.append(text[j + 1])
                        j += 2
                    else:
                        break
                if len(pairs) == 6:
                    flush()
                    tokens.append(("hex", "#" + "".join(pairs)))
                    i = j
                    continue
            if code in "0123456789abcdef":
                flush()
                tokens.append(("color", code))
                i += 2
                continue
            if code in "lmno":
                flush()
                tokens.append(("style", code))
                i += 2
                continue
            if code == 'k':
                flush()
                tokens.append(("skip",))
                i += 2
                continue
            if code == 'r':
                flush()
                tokens.append(("reset",))
                i += 2
                continue
        buf.append(text[i])
        i += 1
    flush()
    return tokens


def clean_mc_codes(text):
    """Return *text* with every Minecraft formatting code removed."""
    return "".join(t[1] for t in _mc_tokens(text) if t[0] == "text")


def mc_to_rich(text):
    """Convert Minecraft formatting codes into Rich markup."""
    parts = []
    open_tags = 0

    def close_all():
        nonlocal open_tags
        while open_tags:
            parts.append("[/]")
            open_tags -= 1

    for tok in _mc_tokens(text):
        kind = tok[0]
        if kind == "hex":
            close_all()
            parts.append(f"[{tok[1]}]")
            open_tags += 1
        elif kind == "color":
            close_all()
            parts.append(f"[{mc_colors[tok[1]]}]")
            open_tags += 1
        elif kind == "style":
            parts.append(f"[{mc_colors[tok[1]]}]")
            open_tags += 1
        elif kind == "reset":
            close_all()
        elif kind == "text":
            parts.append(escape(tok[1]))
    close_all()
    return "".join(parts)
