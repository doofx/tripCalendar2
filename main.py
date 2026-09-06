#!/usr/bin/env python3
"""Entry point for the Trip Calendar GUI.

    python main.py                          # open trip_calendar.xml (or start fresh)
    python main.py my_trip.xml              # open a specific plan
    python main.py my_trip.xml --export out.jpg   # render to JPG without a window
"""

from __future__ import annotations

import argparse
import sys

from tripcalendar import __version__, config, imaging
from tripcalendar.version import BUILD_TIMESTAMP


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="trip-calendar",
        description="Plan a trip on a week-per-row calendar of editable day boxes.",
    )
    parser.add_argument(
        "config",
        nargs="?",
        default=config.DEFAULT_CONFIG_PATH,
        help=f"XML plan to open (default: {config.DEFAULT_CONFIG_PATH})",
    )
    parser.add_argument(
        "--export",
        metavar="FILE.jpg",
        help="render the calendar to a JPG and exit, without opening a window",
    )
    parser.add_argument(
        "--scale",
        type=float,
        default=2.0,
        help="resolution multiplier for --export (default: 2.0)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"Trip Calendar {__version__} (built {BUILD_TIMESTAMP})",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        doc = config.load(args.config)
    except config.ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.export:
        try:
            written = imaging.render(doc, args.export, scale=args.scale)
        except (imaging.ExportError, OSError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 3
        print(f"Wrote {written}")
        return 0

    try:
        from tripcalendar import ui
    except ImportError as exc:  # tkinter missing from the interpreter
        print(
            "error: this Python has no tkinter, which the GUI needs.\n"
            "       Debian/Ubuntu: sudo apt install python3-tk\n"
            "       Fedora:        sudo dnf install python3-tkinter\n"
            "       macOS/Windows: use the python.org installer, which bundles it.\n"
            f"       ({exc})",
            file=sys.stderr,
        )
        return 4

    ui.run(doc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
