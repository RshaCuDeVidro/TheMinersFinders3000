"""Textual widgets: server details panel and the help modal."""

import json

from rich.markup import escape
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Collapsible, Input, Static, Switch

from .constants import STATE_STYLE
from .formatting import latency_style, player_bar
from .motd import mc_to_rich

HELP_TEXT = """[bold #d946ef]TheMinersFinder3000[/] [#6b7280]— help[/]

[bold #9333ea]navigation[/]
  [#e5e7eb]/[/] or [#e5e7eb]f[/]   focus search      [#e5e7eb]Esc[/]   clear search
  [#e5e7eb]Enter[/]    focus table       [#e5e7eb]?[/]     this help
  [#e5e7eb]↑ ↓[/]     move selection    [#e5e7eb]q[/]     quit
  [#e5e7eb]Ctrl+P[/]  command palette (search all actions)

[bold #9333ea]views (tabs)[/]
  [#e5e7eb]1[/] all   [#e5e7eb]2[/] modded   [#e5e7eb]3[/] whitelist   [#e5e7eb]4[/] starred
  shortcuts: [#e5e7eb]d[/] modded, [#e5e7eb]w[/] whitelist

[bold #9333ea]pagination[/] [#6b7280](200 per page)[/]
  [#e5e7eb][[/] / [#e5e7eb]][/]  previous / next page    [#e5e7eb]Home[/] / [#e5e7eb]End[/]  first / last
  or use the buttons under the table

[bold #9333ea]sorting[/]
  [#e5e7eb]s[/] players   [#e5e7eb]p[/] ping   [#e5e7eb]v[/] version   [#e5e7eb]n[/] name
  click a column header; press again to reverse

[bold #9333ea]actions[/]
  [#e5e7eb]*[/] star   [#e5e7eb]c[/] copy ip   [#e5e7eb]m[/] copy mods   [#e5e7eb]t[/] copy motd
  [#e5e7eb]r[/] rescan selected   [#e5e7eb]u[/] rescan failed
  [#e5e7eb]e[/] export json   [#e5e7eb]x[/] export csv
  [#e5e7eb]o[/] settings (or the settings button)

[bold #9333ea]filter (query)[/]
  free text + [#e5e7eb]key:value[/] terms combined with AND:
  [#06b6d4]mod:create[/]  [#06b6d4]ver:1.20[/]  [#06b6d4]host:mc.[/]  [#06b6d4]players:>20[/]
  [#06b6d4]ping:<50[/]  [#06b6d4]wl:yes[/]  [#06b6d4]state:failed[/]  [#06b6d4]err:timeout[/]  [#06b6d4]starred:1[/]
"""


class HelpScreen(ModalScreen):
    BINDINGS = [
        Binding("escape", "dismiss_help", "close", show=False),
        Binding("q", "dismiss_help", "close", show=False),
        Binding("question_mark", "dismiss_help", "close", show=False),
    ]

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="help"):
            yield Static(HELP_TEXT)

    def action_dismiss_help(self):
        self.app.pop_screen()


class SettingsScreen(ModalScreen):
    """Modal to tweak runtime settings (threads, timeout, page size, port)."""

    BINDINGS = [Binding("escape", "dismiss", "close", show=False)]

    def __init__(self, values):
        super().__init__()
        self.values = values

    def compose(self) -> ComposeResult:
        with Vertical(id="settings"):
            yield Static("[bold #d946ef]settings[/]", id="settings_title")
            yield Static("[#6b7280]changes apply immediately to the running session[/]", id="settings_sub")
            with Horizontal(classes="set_row"):
                yield Static("concurrency (threads)")
                yield Input(value=str(self.values["concurrency"]), id="set_concurrency", type="integer")
            with Horizontal(classes="set_row"):
                yield Static("timeout (seconds)")
                yield Input(value=str(self.values["timeout"]), id="set_timeout", type="number")
            with Horizontal(classes="set_row"):
                yield Static("page size (rows)")
                yield Input(value=str(self.values["page_size"]), id="set_page_size", type="integer")
            with Horizontal(classes="set_row"):
                yield Static("default port")
                yield Input(value=str(self.values["default_port"]), id="set_default_port", type="integer")
            with Horizontal(classes="set_row"):
                yield Static("whitelist probe")
                yield Switch(value=bool(self.values.get("probe_whitelist", True)), id="set_probe_whitelist")
            with Horizontal(id="settings_buttons"):
                yield Button("reset", id="set_reset")
                yield Button("cancel", id="set_cancel", variant="error")
                yield Button("save", id="set_save", variant="success")

    def _int(self, selector, default):
        try:
            return int(self.query_one(selector, Input).value)
        except Exception:
            return default

    def _float(self, selector, default):
        try:
            return float(self.query_one(selector, Input).value)
        except Exception:
            return default

    def _collect(self):
        try:
            probe = self.query_one("#set_probe_whitelist", Switch).value
        except Exception:
            probe = self.values.get("probe_whitelist", True)
        return {
            "concurrency": self._int("#set_concurrency", self.values["concurrency"]),
            "timeout": self._float("#set_timeout", self.values["timeout"]),
            "page_size": self._int("#set_page_size", self.values["page_size"]),
            "default_port": self._int("#set_default_port", self.values["default_port"]),
            "probe_whitelist": probe,
        }

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "set_save":
            self.app.apply_settings(self._collect())
            self.app.pop_screen()
        elif bid == "set_reset":
            self.app.apply_settings({"concurrency": 400, "timeout": 2.0, "page_size": 200,
                                     "default_port": 25565, "probe_whitelist": True})
            self.app.pop_screen()
        else:
            self.app.pop_screen()


class ServerDetails(Vertical):
    def compose(self) -> ComposeResult:
        yield Static("[italic #6b7280]select a server to view details[/]", id="d_info")
        yield Static("", id="d_bar")
        with Collapsible(title="motd", collapsed=False):
            yield Static("", id="d_motd")
        with Collapsible(title="mods", collapsed=False):
            yield Static("", id="d_mods")
        with Collapsible(title="players", collapsed=False):
            yield Static("", id="d_players")
        with Collapsible(title="raw", collapsed=True):
            yield Static("", id="d_raw")

    def update_details(self, e):
        info = self.query_one("#d_info", Static)
        bar = self.query_one("#d_bar", Static)
        motd = self.query_one("#d_motd", Static)
        mods_w = self.query_one("#d_mods", Static)
        players_w = self.query_one("#d_players", Static)
        raw_w = self.query_one("#d_raw", Static)

        if not e:
            info.update("[italic #6b7280]select a server to view details[/]")
            for w in (bar, motd, mods_w, players_w, raw_w):
                w.update("")
            return

        state = e.get("state", "queued")
        glyph, gcolor = STATE_STYLE.get(state, ("?", "#6b7280"))
        wl = e.get("whitelist", "unknown")
        wl_color, wl_text = {"yes": ("#f43f5e", "yes"), "no": ("#22c55e", "no")}.get(wl, ("#6b7280", "unknown"))
        star = "[#eab308]★ starred[/] " if e.get("starred") else ""
        lat = e.get("latency")
        lat_txt = f"[{latency_style(lat)}]{lat:.2f}ms[/]" if lat is not None else "[#6b7280]—[/]"
        err = e.get("error")
        err_line = f"\n[#6b7280]error    [/] [#f43f5e]{escape(err)}[/]" if (state == "failed" and err) else ""

        info.update(
            f"{star}[bold #d946ef]{escape(e['host'])}[/]\n"
            f"[#3a1a5c]{'─' * 28}[/]\n"
            f"[#6b7280]state    [/] [{gcolor}]{glyph} {state}[/]\n"
            f"[#6b7280]version  [/] [#06b6d4]{escape(e.get('version') or '—')}[/]\n"
            f"[#6b7280]latency  [/] {lat_txt}\n"
            f"[#6b7280]whitelist[/] [{wl_color}]{wl_text}[/]"
            f"{err_line}"
        )
        bar.update(f"[#6b7280]players  [/] {player_bar(e.get('online', 0), e.get('max', 0))}")

        motd.update(mc_to_rich(e.get("motd_raw", "")) or "[#6b7280]—[/]")

        mods = e.get("mods") or []
        if mods:
            body = "\n".join(f"  [#9333ea]•[/] {escape(m)}" for m in mods[:40])
            if len(mods) > 40:
                body += f"\n  [#6b7280]... and {len(mods) - 40} more[/]"
        else:
            body = "[#6b7280]vanilla server[/]"
        mods_w.update(body)

        players = [p for p in (e.get("players_sample") or []) if p.strip()]
        players_w.update(
            "\n".join(f"  [#9333ea]•[/] {escape(p)}" for p in players)
            if players else "[#6b7280]no players online[/]"
        )

        raw_w.update(escape(json.dumps(
            {k: v for k, v in e.items() if k != "_search"},
            indent=2, ensure_ascii=False,
        )))
