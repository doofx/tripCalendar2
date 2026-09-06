"""Where the application keeps its files.

Everything lives in a ``config`` folder next to the application itself, never in
the current working directory. That matters because the app is normally started
by double-clicking or from an IDE, where the working directory is somewhere the
user has no reason to look — a plan saved there is a plan they cannot find
again.

There is always a config file in use: :func:`ensure_plan` creates one on first
run, so the app is never in a state where "Save" has nowhere to go.
"""

from __future__ import annotations

import os
import sys

CONFIG_DIR_NAME = "config"
DEFAULT_PLAN_NAME = "trip_calendar.xml"
APP_STATE_NAME = "app_state.xml"


def app_dir() -> str:
    """The application's own directory, whether run from source or frozen."""
    if getattr(sys, "frozen", False):  # PyInstaller and friends
        return os.path.dirname(os.path.abspath(sys.executable))
    package = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(package)


def config_dir() -> str:
    return os.path.join(app_dir(), CONFIG_DIR_NAME)


def ensure_config_dir() -> str:
    directory = config_dir()
    os.makedirs(directory, exist_ok=True)
    return directory


def default_plan_path() -> str:
    return os.path.join(config_dir(), DEFAULT_PLAN_NAME)


def app_state_path() -> str:
    return os.path.join(config_dir(), APP_STATE_NAME)


def resolve(path: str | None) -> str:
    """Turn whatever the user typed into an absolute path.

    A path that names a directory component is honoured as given, relative to
    the working directory as any command-line tool would. A bare filename that
    does not exist in the working directory is taken to mean a plan in the
    config folder, so ``trip.xml`` finds ``config/trip.xml``.
    """
    if not path:
        return default_plan_path()
    if os.path.isabs(path):
        return os.path.normpath(path)
    if os.path.dirname(path) or os.path.exists(path):
        return os.path.abspath(path)
    return os.path.join(config_dir(), path)
