"""Command-line entry point."""

import argparse

from .app import McScanFodaApp
from .constants import DEFAULT_CACHE, DEFAULT_PORT


def build_arg_parser():
    p = argparse.ArgumentParser(
        prog="minersfinder",
        description="TheMinersFinder3000 — Minecraft server scanner",
    )
    p.add_argument("hosts_file", help="file with one host[:port] per line (or JSONL with ip/port)")
    p.add_argument("-t", "--timeout", type=float, default=2.0, help="connection timeout in seconds (default 2.0)")
    p.add_argument("-c", "--concurrency", type=int, default=400, help="max concurrent checks (default 400)")
    p.add_argument("-p", "--port", type=int, default=DEFAULT_PORT, help="default port (default 25565)")
    p.add_argument("--cache", default=DEFAULT_CACHE, help=f"cache file (default {DEFAULT_CACHE})")
    p.add_argument("--no-cache", action="store_true", help="do not load a previous scan")
    p.add_argument("--resume", action="store_true", help="skip hosts already online in the cache")
    p.add_argument("--no-whitelist", dest="whitelist", action="store_false",
                   help="skip the whitelist login probe (faster; fewer connections)")
    p.add_argument("-o", "--out", default=".", help="directory for exports (default .)")
    return p


def main(argv=None):
    args = build_arg_parser().parse_args(argv)
    app = McScanFodaApp(
        args.hosts_file,
        timeout=args.timeout,
        concurrency=args.concurrency,
        default_port=args.port,
        cache_file=args.cache,
        use_cache=not args.no_cache,
        resume=args.resume,
        out_dir=args.out,
        probe_whitelist=args.whitelist,
    )
    app.run()
