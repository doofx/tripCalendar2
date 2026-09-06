"""The app-level state that outlives any one plan.

Kept apart from the plan itself on purpose: moving the window or opening a
different file is not an edit to your trip, so it must never make the plan look
unsaved or prompt on the way out.

    <appState schemaVersion="1" appVersion="1.0.2" savedAt="...">
      <lastFile>C:\\trips\\config\\japan.xml</lastFile>
      <window>1360x880+120+60</window>
    </appState>
"""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from . import paths
from .version import SCHEMA_VERSION, __version__, utc_now_iso


@dataclass
class AppState:
    """Which plan was open last, and where the window was."""

    last_file: str = ""
    window: str = ""

    def remember(self, plan_path: str) -> None:
        self.last_file = os.path.abspath(plan_path)


def load(path: str | None = None) -> AppState:
    """Read the app state, returning an empty one if it is missing or broken."""
    target = path or paths.app_state_path()
    if not os.path.exists(target):
        return AppState()
    try:
        root = ET.parse(target).getroot()
    except (ET.ParseError, OSError):
        return AppState()  # a corrupt state file must never block startup
    if root.tag != "appState":
        return AppState()

    def text(tag: str) -> str:
        node = root.find(tag)
        return (node.text or "").strip() if node is not None else ""

    return AppState(last_file=text("lastFile"), window=text("window"))


def save(state: AppState, path: str | None = None) -> str:
    target = path or paths.app_state_path()
    root = ET.Element(
        "appState",
        {
            "schemaVersion": str(SCHEMA_VERSION),
            "appVersion": __version__,
            "savedAt": utc_now_iso(),
        },
    )
    ET.SubElement(root, "lastFile").text = state.last_file
    ET.SubElement(root, "window").text = state.window

    os.makedirs(os.path.dirname(os.path.abspath(target)), exist_ok=True)
    tmp = f"{target}.tmp"
    ET.ElementTree(root).write(tmp, encoding="utf-8", xml_declaration=True)
    os.replace(tmp, target)
    return target


def startup_plan_path(argument: str | None = None, state: AppState | None = None) -> str:
    """Decide which plan to open: the argument, else the last one, else default.

    A remembered file that has since been deleted or moved falls back to the
    default rather than starting the app pointed at something that is not there.
    """
    if argument:
        return paths.resolve(argument)
    current = state if state is not None else load()
    if current.last_file and os.path.exists(current.last_file):
        return os.path.abspath(current.last_file)
    return paths.default_plan_path()
