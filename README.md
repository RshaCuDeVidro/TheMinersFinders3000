# TheMinersFinder3000

**English** · [Português (BR)](README.pt-BR.md)

![screenshot](docs/screenshot.png)

A fast, asynchronous Minecraft (Java) server scanner with a terminal UI. It reads a list of `host[:port]`, shows **status, version, players, latency, mods and whitelist** in real time, and supports query filters, sorting, favorites and export. A local cache lets you resume large scans.

## Features

- **Async scan** with configurable concurrency.
- **Per-host state**: `queued → scanning → online / failed` (offline/failed hosts stay visible).
- **Failure reasons**: each failed host records why (`timeout`, `refused`, `reset`, `dns`, `io`), shown in the details panel and filterable with `err:<reason>`.
- **Whitelist detection** by attempting a login and reading the disconnect reason.
- **Mod detection** (Forge `forgeData` and `modinfo`/`modList`).
- **Colored MOTD** — supports legacy `§` codes, modern hex `§x§R§R§G§G§B§B`, uppercase codes and `§k`.
- **Query filter**: `mod:create`, `ver:1.20`, `players:>20`, `ping:<50`, `wl:yes`, `state:failed`, `starred:1` plus free text.
- **Tabs**: all / modded / whitelist / starred.
- **Pagination**: 200 rows per page (`[` / `]`, `Home` / `End`, or the on-screen buttons) so the UI stays fast on huge lists.
- **Settings menu**: tune concurrency (threads), timeout, page size and default port on the fly.
- **Live progress bar** with percentage/ETA while scanning.
- **Sorting** by players, ping, version or name (also by clicking the column header).
- **Cache** (`.mcscan_cache.json`) with autosave and `--resume`.
- **Export** to JSON and CSV; copy IP, mods and MOTD.
- **Theme**: neon fuchsia / purple / cyan.

## Install

Requires **Python 3.10+**.

```bash
# from source
pip install -r requirements.txt   # or: pip install mcstatus textual

# or install the package (creates the `minersfinder` command)
pip install -e .
```

Dependencies: [`mcstatus`](https://github.com/py-mine/mcstatus) and [`textual`](https://github.com/Textualize/textual).

## Usage

```bash
# as a module
python -m minersfinder hosts.txt

# installed command (pip install -e .)
minersfinder hosts.txt

# compatibility shim (the original command still works)
python3 main.py hosts.txt
```

Hosts file format (see `hosts.example.txt`):

```
play.example.com
mc.example.net:25566
[2001:db8::1]:25565
{"ip": "10.0.0.5", "port": 25565}
```

### CLI options

| Flag | Default | Description |
|---|---|---|
| `-t, --timeout` | `2.0` | Connection timeout (seconds) |
| `-c, --concurrency` | `400` | Max concurrent checks |
| `-p, --port` | `25565` | Default port |
| `--cache` | `.mcscan_cache.json` | Cache file |
| `--no-cache` | — | Do not load a previous scan |
| `--resume` | — | Skip hosts already online in the cache |
| `--no-whitelist` | — | Skip the whitelist login probe (faster; fewer connections) |
| `-o, --out` | `.` | Export directory |

## Keybindings

| Key | Action |
|---|---|
| `/` or `f` | Focus search |
| `Esc` | Clear search |
| `Enter` | Focus table |
| `?` | Help |
| `↑ ↓` | Navigate |
| `1 2 3 4` | Tabs: all / modded / whitelist / starred (`d` / `w` shortcuts) |
| `[` / `]` | Previous / next page |
| `Home` / `End` | First / last page |
| `o` | Settings (threads, timeout, page size, port) |
| `s p v n` | Sort by players / ping / version / name |
| `*` | Star |
| `c m t` | Copy IP / mods / MOTD |
| `r` / `u` | Rescan selected / rescan failed |
| `e` / `x` | Export JSON / CSV |
| `q` | Quit |

## Query filter

Space-separated terms combined with **AND**. A bare term is a free-text match; `key:value` filters a field:

```
mod:create            # mods containing "create"
ver:1.20              # version contains 1.20
host:mc.              # host contains "mc."
players:>20           # operators: > < >= <= =
ping:<50
wl:yes                # yes / no / unknown (y/n/?)
state:failed          # queued / scanning / online / failed
err:timeout           # timeout / refused / reset / dns / io
starred:1
```

Example: `mod:create players:>10 ping:<80` shows modded servers with Create, 10+ players and low ping.

## Project layout

```
minersfinder/
├── __init__.py      # version
├── __main__.py      # python -m minersfinder
├── cli.py           # argparse / entry point
├── app.py           # Textual app (UI, scan, cache, export)
├── app.tcss         # Textual theme/CSS
├── widgets.py       # details panel + help modal
├── scanner.py       # check_host() and hosts-file parsing
├── protocol.py      # VarInt, handshake and whitelist probe
├── motd.py          # Minecraft color-code parser
├── query.py         # filter language
├── models.py        # server entry model
├── cache.py         # JSON cache load/save
├── formatting.py    # Rich helpers (latency, player bar)
├── util.py          # clipboard
└── constants.py     # constants and state palette
```

The `main.py` file at the repository root is just a compatibility shim.

## License

MIT — see [LICENSE](LICENSE).
