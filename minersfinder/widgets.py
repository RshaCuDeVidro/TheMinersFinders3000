"""Textual widgets: server details panel and the help modal."""

import json

from rich.markup import escape
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Collapsible, Static

from .constants import STATE_STYLE
from .formatting import latency_style, player_bar
from .motd import mc_to_rich

HELP_TEXT = """[bold #d946ef]TheMinersFinder3000[/] [#6b7280]— help[/]

[bold #9333ea]navegação[/]
  [#e5e7eb]/[/] ou [#e5e7eb]f[/]   focar busca          [#e5e7eb]Esc[/]   limpar busca
  [#e5e7eb]Enter[/]       focar tabela         [#e5e7eb]?[/]     esta ajuda
  [#e5e7eb]↑ ↓[/]         mover seleção        [#e5e7eb]q[/]     sair

[bold #9333ea]views (abas)[/]
  [#e5e7eb]1[/] all   [#e5e7eb]2[/] modded   [#e5e7eb]3[/] whitelist   [#e5e7eb]4[/] starred
  atalhos: [#e5e7eb]d[/] modded, [#e5e7eb]w[/] whitelist

[bold #9333ea]ordenação[/]
  [#e5e7eb]s[/] players   [#e5e7eb]p[/] ping   [#e5e7eb]v[/] version   [#e5e7eb]n[/] nome
  clique no cabeçalho da coluna; repita para inverter

[bold #9333ea]ações[/]
  [#e5e7eb]*[/] favoritar   [#e5e7eb]c[/] copiar ip   [#e5e7eb]m[/] copiar mods   [#e5e7eb]t[/] copiar motd
  [#e5e7eb]r[/] rescan selecionado   [#e5e7eb]u[/] rescan falhos
  [#e5e7eb]e[/] export json   [#e5e7eb]x[/] export csv

[bold #9333ea]filtro (query)[/]
  texto livre + termos [#e5e7eb]chave:valor[/] combinados com AND:
  [#06b6d4]mod:create[/]  [#06b6d4]ver:1.20[/]  [#06b6d4]host:mc.[/]  [#06b6d4]players:>20[/]
  [#06b6d4]ping:<50[/]  [#06b6d4]wl:yes[/]  [#06b6d4]state:failed[/]  [#06b6d4]starred:1[/]
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

        info.update(
            f"{star}[bold #d946ef]{escape(e['host'])}[/]\n"
            f"[#3a1a5c]{'─' * 28}[/]\n"
            f"[#6b7280]state    [/] [{gcolor}]{glyph} {state}[/]\n"
            f"[#6b7280]version  [/] [#06b6d4]{escape(e.get('version') or '—')}[/]\n"
            f"[#6b7280]latency  [/] {lat_txt}\n"
            f"[#6b7280]whitelist[/] [{wl_color}]{wl_text}[/]"
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
