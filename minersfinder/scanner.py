"""Async scanning of Minecraft servers."""

import asyncio
import json
import socket

from mcstatus import JavaServer

from .models import new_entry
from .motd import clean_mc_codes
from .protocol import check_whitelist_aggressive, parse_host_port


def classify_error(exc):
    """Map an exception to a short failure reason."""
    name = type(exc).__name__
    if isinstance(exc, asyncio.TimeoutError) or "Timeout" in name:
        return "timeout"
    if isinstance(exc, ConnectionRefusedError):
        return "refused"
    if isinstance(exc, ConnectionResetError):
        return "reset"
    if isinstance(exc, socket.gaierror):
        return "dns"
    if isinstance(exc, OSError):
        return "io"
    return name


def read_hosts_file(path, default_port):
    """Parse a hosts file.

    Each line is ``host[:port]`` or a JSON object with ``ip``/``port``.
    Returns ``(hosts, malformed)`` where *hosts* is de-duplicated and ordered.
    """
    hosts = []
    malformed = 0
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("{"):
                try:
                    data = json.loads(line)
                    hosts.append(f"{data['ip']}:{data.get('port', default_port)}")
                except (json.JSONDecodeError, KeyError, TypeError):
                    malformed += 1
            else:
                hosts.append(line if (":" in line or line.startswith("[")) else f"{line}:{default_port}")
    return list(dict.fromkeys(hosts)), malformed


async def check_host(host, timeout=2.0, probe_whitelist=True):
    """Query a single server.

    Returns an entry dict. On success ``state == "online"``; on failure
    ``state == "failed"`` with an ``error`` reason (timeout/refused/reset/dns).

    When *probe_whitelist* is false the (second) login probe is skipped and the
    whitelist stays ``"unknown"``, halving the connections made per host.
    """
    try:
        addr, port = parse_host_port(host)
        server = await JavaServer.async_lookup(host, timeout=timeout)
        status = await server.async_status()
        raw = status.raw
        motd_raw = status.description
        if isinstance(motd_raw, dict):
            motd_raw = motd_raw.get('text', '')
        elif hasattr(motd_raw, 'raw'):
            motd_raw = str(motd_raw.raw) if isinstance(motd_raw.raw, str) else json.dumps(motd_raw.raw)
        else:
            motd_raw = str(motd_raw)

        found_mods = []
        if 'modinfo' in raw and 'modList' in raw['modinfo']:
            found_mods = [m['modid'] for m in raw['modinfo']['modList']]
        elif 'forgeData' in raw and 'mods' in raw['forgeData']:
            found_mods = [m['modId'] for m in raw['forgeData']['mods']]

        whitelist = (await check_whitelist_aggressive(addr, port, timeout)
                     if probe_whitelist else "unknown")
        sample = [p.name for p in (status.players.sample or [])]
        return {
            "host": host,
            "state": "online",
            "version": str(status.version.name),
            "online": status.players.online,
            "max": status.players.max,
            "motd_raw": motd_raw,
            "motd_clean": clean_mc_codes(motd_raw).lower(),
            "latency": status.latency,
            "players_sample": sample,
            "mods": found_mods,
            "whitelist": whitelist,
            "starred": False,
            "error": None,
        }
    except Exception as exc:
        entry = new_entry(host)
        entry["state"] = "failed"
        entry["error"] = classify_error(exc)
        return entry
