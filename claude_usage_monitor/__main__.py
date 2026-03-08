"""Allow running as `python -m claude_usage_monitor`."""

import argparse
import sys


def _entry():
    parser = argparse.ArgumentParser(
        description="Claude Code Usage Monitor — system tray app or CLI reporter",
    )
    parser.add_argument(
        "--cli",
        action="store_true",
        help="Print current usage stats to stdout and exit (no GUI)",
    )
    args = parser.parse_args()

    if args.cli:
        from .cli import cli_report
        sys.exit(cli_report())
    else:
        from .app import main
        main()


if __name__ == "__main__":
    _entry()
