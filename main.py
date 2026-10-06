"""Backwards-compatible entry point.

The project now lives in the :mod:`minersfinder` package; this shim keeps the
old ``python3 mcscanfoda.py hosts.txt`` invocation working.
"""

from minersfinder.cli import main

if __name__ == "__main__":
    main()
