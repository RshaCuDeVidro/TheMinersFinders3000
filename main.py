"""Convenience entry point.

The project lives in the :mod:`minersfinder` package; this shim lets you run
``python3 main.py hosts.txt`` from the repository root.
"""

from minersfinder.cli import main

if __name__ == "__main__":
    main()
