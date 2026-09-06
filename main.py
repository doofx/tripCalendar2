#!/usr/bin/env python3
"""Entry point for the Trip Calendar GUI.

    python main.py                              # reopen the last plan you had open
    python main.py config/example_trip.xml      # open a specific plan
    python main.py japan.xml                    # a bare name means config/japan.xml
    python main.py --export out.jpg             # render to JPG without a window

Plans live in the ``config`` folder next to this file, so a saved plan is always
somewhere findable no matter which directory the app was started from.
"""

from __future__ import annotations

import argparse
import sys

from tripcalendar import __version__, config, imaging, paths, session
from tripcalendar.version import BUILD_TIMESTAMP


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="trip-calendar",
        description="Plan a trip on a week-per-row calendar of editable day boxes.",
        epilog=f"Plans and settings are kept in: {paths.config_dir()}",
    )
    parser.add_argument(
        "plan",
        nargs="?",
        default=None,
        help="XML plan to open; a bare filename is looked up in the config folder "
        "(default: the plan you had open last, otherwise config/trip_calendar.xml)",
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
        "--config-dir",
        action="store_true",
        help="print the folder holding plans and settings, then exit",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"Trip Calendar {__version__} (built {BUILD_TIMESTAMP})",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.config_dir:
        print(paths.config_dir())
        return 0

    state = session.load()
    plan_path = session.startup_plan_path(args.plan, state)

    try:
        # Creates the file when it is not there yet, so there is always a config
        # file in use and "Save" always has a destination.
        doc = config.ensure_plan(plan_path)
    except (config.ConfigError, OSError) as exc:
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

    # Reopening this plan next time is the expected behaviour, so record it now
    # rather than only on a successful save.
    state.remember(doc.path)
    try:
        session.save(state)
    except OSError:
        pass  # a read-only config folder must not stop the app from starting

    ui.run(doc, state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
