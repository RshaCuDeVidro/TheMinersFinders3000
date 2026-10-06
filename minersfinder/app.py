"""The Textual application: TheMinersFinder3000 TUI."""

import asyncio
import csv
import json
import time
from collections import deque
from datetime import datetime
from pathlib import Path

from rich.markup import escape
from rich.style import Style
from rich.text import Text as RichText
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import DataTable, Footer, Header, Input, ProgressBar, Static, Tab, Tabs

from . import cache as cache_mod
from .constants import (
    AUTOSAVE_INTERVAL, DEFAULT_CACHE, DEFAULT_PORT, DIRTY_BATCH,
    MAX_DISPLAY_ROWS, MAX_PLACEHOLDER_ROWS, REFRESH_INTERVAL, STATE_STYLE,
)
from .formatting import latency_style
from .models import new_entry, search_blob
from .motd import clean_mc_codes
from .query import parse_query
from .scanner import check_host, read_hosts_file
from .util import copy_to_clipboard
from .widgets import HelpScreen, ServerDetails

_CELL_CACHE = {}


def _cell(value, style):
    key = (value, style)
    cached = _CELL_CACHE.get(key)
    if cached is None:
        cached = RichText(value, style=style)
        if len(_CELL_CACHE) < 20000:
            _CELL_CACHE[key] = cached
    return cached


_STYLE_STAR = Style.parse("#eab308")
_STYLE_DOT = Style.parse("#2a2a3a")
_STYLE_HOST = Style.parse("bold #e5e7eb")
_STYLE_HOST_BAD = Style.parse("#6b7280")


class McScanFodaApp(App):
    TITLE = "TheMinersFinder3000"
    SUB_TITLE = "minecraft server scanner"
    CSS_PATH = Path(__file__).with_name("app.tcss")

    BINDINGS = [
        Binding("q", "quit", "exit"),
        Binding("slash", "focus_filter", "search"),
        Binding("f", "focus_filter", "search", show=False),
        Binding("escape", "clear_filter", "clear"),
        Binding("enter", "focus_table", "table"),
        Binding("question_mark", "help", "help"),
        Binding("1", "view_all", "all"),
        Binding("2", "view_modded", "modded"),
        Binding("3", "view_whitelist", "wl"),
        Binding("4", "view_starred", "star"),
        Binding("d", "view_modded", "modded", show=False),
        Binding("w", "view_whitelist", "wl", show=False),
        Binding("s", "sort_players", "sort ply"),
        Binding("p", "sort_ping", "sort ping"),
        Binding("v", "sort_version", "sort ver"),
        Binding("n", "sort_name", "sort name"),
        Binding("asterisk", "toggle_star", "star"),
        Binding("c", "copy_ip", "ip"),
        Binding("m", "copy_mods", "mods"),
        Binding("t", "copy_motd", "motd"),
        Binding("r", "rescan_selected", "rescan"),
        Binding("u", "rescan_failed", "rescan failed"),
        Binding("e", "export_json", "json"),
        Binding("x", "export_csv", "csv"),
    ]

    def __init__(self, hosts_file, timeout=2.0, concurrency=400, default_port=DEFAULT_PORT,
                 cache_file=DEFAULT_CACHE, use_cache=True, resume=False, out_dir="."):
        super().__init__()
        self.hosts_file = hosts_file
        self.timeout = timeout
        self.concurrency = concurrency
        self.default_port = default_port
        self.cache_file = cache_file
        self.use_cache = use_cache
        self.resume = resume
        self.out_dir = Path(out_dir)

        self.all_entries = []
        self.by_host = {}
        self.row_keys = {}
        self.col_keys = []
        self.online_count = 0
        self.failed_count = 0
        self.total_hosts = 0
        self.completed_count = 0

        self.view = "all"
        self.sort_key = None
        self.sort_desc = False
        self._selected = None
        self._filter_pred = parse_query("")
        self._last_query_text = ""
        self._filter_timer = None
        self._refresh_timer = None
        self._save_timer = None
        self._cache_dirty = False
        self._scanning = False
        self._progress_active = False
        self._scan_start = None
        self._dirty = set()
        self._row_gen = 0
        self._rebuilding = False
        self._rebuild_pending = False
        self._last_progress = -1
        self._status_text = None
        self._rebuild_pos = 0
        self._rebuild_selected = None
        self._rebuild_count = 0
        self._rebuild_truncated = False
        self._cap_notified = False
        self._rate_times = deque(maxlen=200)

    # ------------------------------------------------------------ compose
    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("starting...", id="status_bar")
        with Horizontal(id="header_area"):
            yield Input(placeholder="search  ·  mod:create  ver:1.20  players:>20  state:failed ...", id="filter_input")
        yield Tabs(
            Tab("all", id="all"),
            Tab("modded", id="modded"),
            Tab("whitelist", id="whitelist"),
            Tab("starred", id="starred"),
            active="all", id="view_tabs",
        )
        with Horizontal(id="main"):
            with Vertical(id="left_pane"):
                yield DataTable(id="server_table")
            with VerticalScroll(id="right_pane"):
                yield ServerDetails(id="details")
        yield ProgressBar(id="progress", show_eta=True, show_percentage=True)
        yield Footer()

    async def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.cursor_type = "row"
        self.col_keys = [
            table.add_column("host", width=31),
            table.add_column("version", width=14),
            table.add_column("load", width=18),
            table.add_column("wl", width=3),
            table.add_column("mods", width=8),
        ]
        self.query_one("#filter_input").border_title = "search"
        self.query_one("#left_pane").border_title = "servers"
        self.query_one("#right_pane").border_title = "details"
        if self.use_cache:
            self.load_cache()
        self.run_worker(self.scan_servers(), exclusive=True)
        self._refresh_timer = self.set_interval(REFRESH_INTERVAL, self.refresh_ui)
        self._save_timer = self.set_interval(AUTOSAVE_INTERVAL, self._autosave_tick)
        self.call_after_refresh(self._apply_column_widths)
        self._update_status()

    def _apply_column_widths(self):
        try:
            pane = self.query_one("#left_pane").size.width
            table = self.query_one(DataTable)
        except Exception:
            return
        if pane <= 0:
            return
        others = 14 + 18 + 3 + 8
        overhead = 2 * (len(self.col_keys) - 1)
        host_w = max(12, pane - others - overhead - 1)
        try:
            table.columns[self.col_keys[0]].width = host_w
        except Exception:
            pass

    # ------------------------------------------------------------- cache
    def load_cache(self):
        try:
            servers = cache_mod.load_cache(self.cache_file)
        except Exception as e:
            self.notify(f"cache error: {e}", severity="warning")
            return
        for r in servers:
            self._index_result(r)
        if self.all_entries:
            self.online_count = sum(1 for e in self.all_entries if e["state"] == "online")
            self.failed_count = sum(1 for e in self.all_entries if e["state"] == "failed")
            self._update_status()
            self.notify(f"loaded {len(self.all_entries)} cached servers")

    def save_cache(self):
        try:
            cache_mod.save_cache(self.cache_file, self.all_entries)
            self._cache_dirty = False
        except Exception as e:
            self.notify(f"cache save error: {e}", severity="warning")

    async def _save_cache_async(self, force=False):
        if not force and not self._cache_dirty:
            return
        self._cache_dirty = False
        payload = cache_mod.dump_entries(list(self.all_entries))

        def _work():
            Path(self.cache_file).write_text(json.dumps(payload))

        try:
            await asyncio.to_thread(_work)
        except Exception as e:
            self.notify(f"cache save error: {e}", severity="warning")

    def _autosave_tick(self):
        if self._cache_dirty:
            self.run_worker(self._save_cache_async(), group="cache", exclusive=True)

    def _index_result(self, r):
        r["_search"] = search_blob(r)
        existing = self.by_host.get(r["host"])
        if existing is not None:
            existing.clear()
            existing.update(r)
        else:
            self.all_entries.append(r)
            self.by_host[r["host"]] = r

    # ------------------------------------------------------------ refresh
    def refresh_ui(self):
        if self._rebuild_pending:
            self._rebuild_step()
        self._flush_dirty()
        if self._progress_active and self.completed_count != self._last_progress:
            self._last_progress = self.completed_count
            try:
                self.query_one(ProgressBar).update(progress=self.completed_count)
            except Exception:
                pass
        self._update_status()

    def _flush_dirty(self, batch=DIRTY_BATCH):
        if self._rebuilding or not self._dirty:
            return
        for host in list(self._dirty)[:batch]:
            self._dirty.discard(host)
            e = self.by_host.get(host)
            if e is not None:
                self._show_entry(e)

    # --------------------------------------------------------------- scan
    def _read_hosts(self):
        try:
            hosts, malformed = read_hosts_file(self.hosts_file, self.default_port)
        except Exception as e:
            self.notify(f"error: {e}", severity="error")
            return None
        if malformed:
            self.notify(f"{malformed} malformed line(s) skipped", severity="warning")
        return hosts

    def _ensure_entries(self, hosts):
        added = False
        for h in hosts:
            if h not in self.by_host:
                e = new_entry(h)
                self.by_host[h] = e
                self.all_entries.append(e)
                added = True
        return added

    def _should_scan(self, host):
        e = self.by_host.get(host)
        if self.resume and e and e.get("state") == "online":
            return False
        return True

    async def scan_servers(self):
        hosts = self._read_hosts()
        if hosts is None:
            return
        self._ensure_entries(hosts)
        self._row_gen += 1
        await self._populate_placeholder_rows(self._row_gen)

        pending = [h for h in hosts if self._should_scan(h)]
        if self.resume:
            skipped = len(hosts) - len(pending)
            if skipped:
                self.notify(f"resume: {skipped} skipped, scanning {len(pending)}")

        self.total_hosts = len(pending)
        self._scanning = True
        self._progress_active = True
        self._scan_start = time.monotonic()
        pb = self.query_one(ProgressBar)
        pb.total = len(pending) or 1
        pb.update(progress=0)
        self._update_status()

        await self._run_pool(pending)

        self._scanning = False
        try:
            pb.update(progress=self.completed_count)
        except Exception:
            pass
        self._progress_active = False
        self._flush_dirty()
        await self._save_cache_async(force=True)
        elapsed = time.monotonic() - self._scan_start
        self._update_status()
        self.notify(f"done! {self.online_count} online | {self.failed_count} failed | {elapsed:.1f}s")

    async def _populate_placeholder_rows(self, gen):
        table = self.query_one(DataTable)
        entries = self.all_entries
        limit = len(entries)
        if limit > MAX_PLACEHOLDER_ROWS:
            self.notify(f"showing first {MAX_PLACEHOLDER_ROWS} of {limit} hosts — use the filter")
            limit = MAX_PLACEHOLDER_ROWS
        n = 0
        for e in entries[:limit]:
            if gen != self._row_gen:
                return
            host = e["host"]
            if host not in self.row_keys and self._visible(e):
                self.row_keys[host] = table.add_row(*self._row_cells(e), key=host)
                n += 1
                if n % 500 == 0:
                    await asyncio.sleep(0)
        await asyncio.sleep(0)

    async def _run_pool(self, hosts):
        if not hosts:
            return
        queue = asyncio.Queue()
        for h in hosts:
            queue.put_nowait(h)
        workers = [
            asyncio.create_task(self._scan_worker(queue))
            for _ in range(max(1, min(self.concurrency, len(hosts))))
        ]
        await asyncio.gather(*workers)

    async def _scan_worker(self, queue):
        while True:
            try:
                host = queue.get_nowait()
            except asyncio.QueueEmpty:
                return
            self._set_state(host, "scanning")
            res = await self.check_server(host)
            self._finish(host, res)
            self._on_progress()

    def _on_progress(self):
        self.completed_count += 1
        self._rate_times.append(time.monotonic())

    def _finish(self, host, res):
        old = self.by_host[host].get("state")
        if res:
            res["starred"] = self.by_host[host].get("starred", False)
            self._index_result(res)
            self._count_transition(old, "online")
        else:
            e = self.by_host[host]
            self._count_transition(old, "failed")
            e["state"] = "failed"
        self._dirty.add(host)
        self._cache_dirty = True

    def _count_transition(self, old, new):
        if old == new:
            return
        if old == "online":
            self.online_count -= 1
        elif old == "failed":
            self.failed_count -= 1
        if new == "online":
            self.online_count += 1
        elif new == "failed":
            self.failed_count += 1

    def _set_state(self, host, state):
        e = self.by_host[host]
        old = e.get("state")
        self._count_transition(old, state)
        e["state"] = state

    async def check_server(self, host):
        return await check_host(host, self.timeout)

    # -------------------------------------------------------------- view
    def _visible(self, e):
        if self.view == "modded" and not (e.get("mods") or []):
            return False
        if self.view == "whitelist" and e.get("whitelist") != "yes":
            return False
        if self.view == "starred" and not e.get("starred"):
            return False
        return self._filter_pred(e)

    def _row_cells(self, e):
        state = e.get("state", "queued")
        glyph, color = STATE_STYLE.get(state, ("?", "#6b7280"))
        mods = e.get("mods") or []
        lat = e.get("latency")
        starred = e.get("starred")
        wl = e.get("whitelist", "unknown")

        host_cell = RichText()
        host_cell.append(glyph, style=color)
        host_cell.append(" ")
        host_cell.append("★" if starred else "·", style=_STYLE_STAR if starred else _STYLE_DOT)
        host_cell.append(" ")
        host_cell.append(e["host"], style=_STYLE_HOST_BAD if state == "failed" else _STYLE_HOST)

        load = RichText()
        load.append(f"{e.get('online', 0)}/{e.get('max', 0)}", style="#e5e7eb")
        load.append(" ")
        load.append(f"{lat:.0f}ms" if lat is not None else "—",
                    style=latency_style(lat) if lat is not None else "#6b7280")

        wl_text, wl_color = {"yes": ("Y", "#f43f5e"), "no": ("N", "#22c55e")}.get(wl, ("?", "#6b7280"))
        return [
            host_cell,
            _cell(e.get("version", "")[:14], "#06b6d4"),
            load,
            _cell(wl_text, wl_color),
            _cell("modded" if mods else "vanilla", "#d946ef" if mods else "#6b7280"),
        ]

    def _sort_value(self, e):
        k = self.sort_key
        if k == "players":
            return e.get("online", 0)
        if k == "ping":
            lat = e.get("latency")
            return lat if lat is not None else 1e9
        if k == "version":
            return e.get("version", "")
        return e.get("host", "")

    def rebuild_rows(self):
        self._row_gen += 1
        self._rebuilding = True
        self._rebuild_pending = True
        self._rebuild_pos = 0
        self._rebuild_selected = self._selected
        self._rebuild_count = 0
        self._rebuild_truncated = False
        self._cap_notified = False
        if self.sort_key:
            self.all_entries.sort(key=self._sort_value, reverse=self.sort_desc)
        try:
            table = self.query_one(DataTable)
            table.clear()
            self.row_keys.clear()
        except Exception:
            self._rebuild_pending = False
            self._rebuilding = False

    def _rebuild_step(self, chunk=500):
        try:
            table = self.query_one(DataTable)
        except Exception:
            self._rebuild_pending = False
            self._rebuilding = False
            return
        entries = self.all_entries
        n = 0
        while self._rebuild_pos < len(entries) and n < chunk:
            e = entries[self._rebuild_pos]
            self._rebuild_pos += 1
            if self._visible(e):
                self.row_keys[e["host"]] = table.add_row(*self._row_cells(e), key=e["host"])
                self._rebuild_count += 1
                n += 1
                if self._rebuild_count >= MAX_DISPLAY_ROWS:
                    self._rebuild_truncated = True
                    self._rebuild_pos = len(entries)
                    break
        if self._rebuild_pos >= len(entries):
            self._rebuild_pending = False
            self._rebuilding = False
            if self._rebuild_truncated and not self._cap_notified:
                self._cap_notified = True
                self.notify(f"showing first {MAX_DISPLAY_ROWS} rows — refine the filter")
            if self._rebuild_selected:
                try:
                    table.move_cursor(row=table.get_row_index(self._rebuild_selected))
                except Exception:
                    pass
            self._update_status()

    def _show_entry(self, e):
        try:
            table = self.query_one(DataTable)
        except Exception:
            return
        host = e["host"]
        row_key = self.row_keys.get(host)
        if self._visible(e):
            cells = self._row_cells(e)
            if row_key is not None:
                try:
                    for col, val in zip(self.col_keys, cells):
                        table.update_cell(row_key, col, val, update_width=False)
                except Exception:
                    try:
                        table.remove_row(row_key)
                    except Exception:
                        pass
                    self.row_keys.pop(host, None)
                    row_key = None
            if row_key is None:
                if len(self.row_keys) >= MAX_DISPLAY_ROWS:
                    return
                self.row_keys[host] = table.add_row(*cells, key=host)
        elif row_key is not None:
            try:
                table.remove_row(row_key)
            except Exception:
                pass
            self.row_keys.pop(host, None)
        if self._selected == host:
            try:
                self.query_one("#details").update_details(e)
            except Exception:
                pass

    def _selected_host(self):
        table = self.query_one(DataTable)
        if table.row_count == 0 or table.cursor_row is None:
            return None
        try:
            return table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value
        except Exception:
            return None

    def _set_view(self, view):
        if self.view == view:
            return
        self.view = view
        try:
            tabs = self.query_one("#view_tabs", Tabs)
            if tabs.active != view:
                tabs.active = view
        except Exception:
            pass
        self.rebuild_rows()
        self._update_status()

    # ------------------------------------------------------------- status
    def _rate(self):
        if not self._scanning or len(self._rate_times) < 2:
            return 0.0
        span = self._rate_times[-1] - self._rate_times[0]
        return (len(self._rate_times) - 1) / span if span > 0 else 0.0

    def _update_status(self):
        queued = max(0, len(self.all_entries) - self.online_count - self.failed_count)
        state = (f"[#06b6d4]● scanning[/] {self._rate():.0f}/s" if self._scanning
                 else "[#22c55e]● idle[/]")
        arrow = ("↓" if self.sort_desc else "↑") if self.sort_key else ""
        sort_txt = f"{self.sort_key} {arrow}".strip() if self.sort_key else "—"
        ftext = self.query_one("#filter_input").value.strip()
        line = (
            f"{state}  [#6b7280]│[/]  "
            f"[#22c55e]{self.online_count}[/] online  "
            f"[#ef4444]{self.failed_count}[/] failed  "
            f"[#6b7280]{queued}[/] queued  [#6b7280]│[/]  "
            f"view [bold #d946ef]{self.view}[/]  sort [bold #d946ef]{sort_txt}[/]"
        )
        if ftext:
            line += f"  filter [bold #9333ea]{escape(ftext)}[/]"
        if line == self._status_text:
            return
        self._status_text = line
        try:
            self.query_one("#status_bar").update(line)
        except Exception:
            self._status_text = None

    # ------------------------------------------------------------- events
    def on_tabs_tab_activated(self, event: Tabs.TabActivated) -> None:
        view = (event.tab.id or "all") if event.tab else "all"
        if view != self.view:
            self.view = view
            self.rebuild_rows()
            self._update_status()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "filter_input":
            if self._filter_timer is not None:
                self._filter_timer.stop()
            self._filter_timer = self.set_timer(0.2, self._recompile_filter)

    def _recompile_filter(self):
        text = self.query_one("#filter_input").value
        if text == self._last_query_text:
            return
        self._last_query_text = text
        self._filter_pred = parse_query(text)
        self.rebuild_rows()
        self._update_status()

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.row_key:
            self._selected = event.row_key.value
            self.query_one("#details").update_details(self.by_host.get(self._selected))

    def on_data_table_header_selected(self, event: DataTable.HeaderSelected) -> None:
        key = event.column_key.value if event.column_key else None
        mapping = {"load": "players", "version": "version", "host": "name"}
        if key in mapping:
            self._sort_by(mapping[key])

    def on_resize(self, event) -> None:
        try:
            self.query_one("#main").set_class(event.size.width < 100, "narrow")
        except Exception:
            pass
        self.call_after_refresh(self._apply_column_widths)

    # ------------------------------------------------------------- actions
    def action_focus_filter(self):
        self.query_one("#filter_input").focus()

    def action_clear_filter(self):
        inp = self.query_one("#filter_input")
        if inp.value:
            inp.value = ""
            self._last_query_text = ""
            self._filter_pred = parse_query("")
            self.rebuild_rows()
            self._update_status()

    def action_focus_table(self):
        self.query_one(DataTable).focus()

    def action_help(self):
        self.push_screen(HelpScreen())

    def action_view_all(self):
        self._set_view("all")

    def action_view_modded(self):
        self._set_view("modded")

    def action_view_whitelist(self):
        self._set_view("whitelist")

    def action_view_starred(self):
        self._set_view("starred")

    def _sort_by(self, key):
        if self.sort_key == key:
            self.sort_desc = not self.sort_desc
        else:
            self.sort_key = key
            self.sort_desc = key in ("players",)
        self.rebuild_rows()
        self._update_status()
        self.notify(f"sorted by {key} {'desc' if self.sort_desc else 'asc'}")

    def action_sort_players(self):
        self._sort_by("players")

    def action_sort_ping(self):
        self._sort_by("ping")

    def action_sort_version(self):
        self._sort_by("version")

    def action_sort_name(self):
        self._sort_by("name")

    def action_toggle_star(self):
        host = self._selected_host()
        if not host:
            return
        e = self.by_host[host]
        e["starred"] = not e.get("starred")
        self._show_entry(e)
        self._cache_dirty = True
        self.notify("starred" if e["starred"] else "unstarred")

    def action_copy_ip(self):
        host = self._selected_host()
        if host:
            copy_to_clipboard(host)
            self.notify(f"copied {host}")

    def action_copy_mods(self):
        host = self._selected_host()
        r = self.by_host.get(host) if host else None
        if r:
            mods = r.get("mods") or []
            copy_to_clipboard("\n".join(mods) if mods else "(vanilla)")
            self.notify(f"copied {len(mods)} mods")

    def action_copy_motd(self):
        host = self._selected_host()
        r = self.by_host.get(host) if host else None
        if r:
            copy_to_clipboard(clean_mc_codes(r.get("motd_raw", "")))
            self.notify("copied motd")

    def action_rescan_selected(self):
        host = self._selected_host()
        if host:
            self.run_worker(self._rescan_one(host), group="rescan", exclusive=True)
            self.notify(f"rescanning {host}...")

    async def _rescan_one(self, host):
        e = self.by_host[host]
        self._set_state(host, "scanning")
        self._show_entry(e)
        res = await self.check_server(host)
        self._finish(host, res)
        self._flush_dirty()
        self._update_status()
        await self._save_cache_async(force=True)

    def action_rescan_failed(self):
        self.run_worker(self._rescan_failed(), group="rescan", exclusive=True)

    async def _rescan_failed(self):
        hosts = [h for h, e in self.by_host.items() if e.get("state") == "failed"]
        if not hosts:
            self.notify("no failed hosts")
            return
        self._scanning = True
        self._update_status()
        await self._run_pool(hosts)
        self._scanning = False
        self._flush_dirty()
        self._update_status()
        await self._save_cache_async(force=True)
        self.notify(f"rescanned {len(hosts)} failed host(s)")

    # ------------------------------------------------------------- export
    def _export_path(self, name):
        self.out_dir.mkdir(parents=True, exist_ok=True)
        return self.out_dir / name

    def action_export_json(self):
        if not self.all_entries:
            self.notify("nothing to export", severity="warning")
            return
        path = self._export_path(f"mc_servers_{datetime.now():%Y%m%d_%H%M%S}.json")
        clean = [{k: v for k, v in e.items() if k != "_search"} for e in self.all_entries]
        try:
            path.write_text(json.dumps(clean, indent=2))
            self.notify(f"saved {path}")
        except Exception as e:
            self.notify(f"export error: {e}", severity="error")

    def action_export_csv(self):
        if not self.all_entries:
            self.notify("nothing to export", severity="warning")
            return
        path = self._export_path(f"mc_servers_{datetime.now():%Y%m%d_%H%M%S}.csv")
        try:
            with path.open("w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["host", "state", "version", "online", "max", "latency_ms",
                            "whitelist", "starred", "mods", "motd"])
                for r in self.all_entries:
                    w.writerow([
                        r["host"], r.get("state", ""), r.get("version", ""),
                        r.get("online", 0), r.get("max", 0),
                        f"{r.get('latency', 0.0):.1f}" if r.get("latency") is not None else "",
                        r.get("whitelist", "unknown"), bool(r.get("starred")),
                        ";".join(r.get("mods") or []), clean_mc_codes(r.get("motd_raw", "")),
                    ])
            self.notify(f"saved {path}")
        except Exception as e:
            self.notify(f"export error: {e}", severity="error")
