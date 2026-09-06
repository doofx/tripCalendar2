"""XML persistence for the trip calendar.

One human-editable XML file holds everything: the weeks to display, the look and
feel, the text of every day, and a rolling log of changes stamped with the
application version and the time they were made.

    <tripCalendar schemaVersion="1" appVersion="1.0.0"
                  revision="7" savedAt="2026-09-06T18:20:11+00:00">
      <settings>
        <startWeek>2023-02-26</startWeek>
        <endWeek>2023-04-01</endWeek>
        ...
      </settings>
      <days>
        <day date="2023-02-28">Flight to Tokyo at 20:00
    Sleep: Tokyo</day>
      </days>
      <history>
        <change revision="7" at="..." version="1.0.0">Moved ... one day forward</change>
      </history>
    </tripCalendar>

``startWeek`` and ``endWeek`` are any date inside the first and last week you
want on screen; they are snapped to week boundaries on load, so writing them by
hand is forgiving.
"""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from typing import Any

from .model import SUNDAY, TripCalendar, WEEKDAY_HEADERS, week_start
from .version import SCHEMA_VERSION, __version__, utc_now_iso

DEFAULT_CONFIG_PATH = "trip_calendar.xml"

#: How many change records to keep in the file before the oldest are dropped.
HISTORY_LIMIT = 100


class ConfigError(Exception):
    """The XML file exists but cannot be understood."""


@dataclass
class Settings:
    """Everything about the calendar that is not day text."""

    start_week: date
    end_week: date
    first_day: str = SUNDAY
    title: str = "Trip Calendar"
    theme: str = "aurora"
    date_format: str = "%d/%m/%Y"
    cell_width: int = 168
    cell_height: int = 132
    font_scale: float = 1.0
    window: str = ""  # last geometry, e.g. "1400x900+120+60"

    def copy(self) -> "Settings":
        return replace(self)


def _default_settings() -> Settings:
    start = week_start(date.today(), SUNDAY)
    return Settings(start_week=start, end_week=start + timedelta(days=27))


@dataclass
class Change:
    """One recorded edit: what happened, in which version, and when."""

    revision: int
    at: str
    version: str
    summary: str


@dataclass
class Document:
    """A loaded XML file: settings, calendar and change history together."""

    settings: Settings
    calendar: TripCalendar
    revision: int = 0
    saved_at: str = ""
    app_version: str = __version__
    history: list[Change] = field(default_factory=list)
    path: str = DEFAULT_CONFIG_PATH

    def record(self, summary: str) -> Change:
        """Append a change record stamped with the version and the time."""
        self.revision += 1
        change = Change(
            revision=self.revision,
            at=utc_now_iso(),
            version=__version__,
            summary=summary,
        )
        self.history.append(change)
        del self.history[:-HISTORY_LIMIT]
        return change

    @property
    def last_change(self) -> Change | None:
        return self.history[-1] if self.history else None

    def sync_settings_from_calendar(self) -> None:
        self.settings.start_week = self.calendar.start
        self.settings.end_week = self.calendar.end
        self.settings.first_day = self.calendar.first_day


# --------------------------------------------------------------------- read


def _text(node: ET.Element | None, default: str = "") -> str:
    if node is None or node.text is None:
        return default
    return node.text.strip()


def _parse_date(raw: str, what: str) -> date:
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise ConfigError(f"{what} must be an ISO date (YYYY-MM-DD), got {raw!r}") from exc


def _parse_number(raw: str, default: Any, cast) -> Any:
    try:
        return cast(raw)
    except (TypeError, ValueError):
        return default


def parse_settings(root: ET.Element) -> Settings:
    node = root.find("settings")
    if node is None:
        raise ConfigError("<settings> section is missing")

    fallback = _default_settings()
    start_raw = _text(node.find("startWeek"))
    end_raw = _text(node.find("endWeek"))
    start = _parse_date(start_raw, "startWeek") if start_raw else fallback.start_week
    end = _parse_date(end_raw, "endWeek") if end_raw else fallback.end_week

    first_day = _text(node.find("firstDayOfWeek"), SUNDAY).lower()
    if first_day not in WEEKDAY_HEADERS:
        first_day = SUNDAY

    return Settings(
        start_week=start,
        end_week=end,
        first_day=first_day,
        title=_text(node.find("title"), fallback.title) or fallback.title,
        theme=_text(node.find("theme"), fallback.theme).lower() or fallback.theme,
        date_format=_text(node.find("dateFormat"), fallback.date_format)
        or fallback.date_format,
        cell_width=_parse_number(_text(node.find("cellWidth")), fallback.cell_width, int),
        cell_height=_parse_number(
            _text(node.find("cellHeight")), fallback.cell_height, int
        ),
        font_scale=_parse_number(_text(node.find("fontScale")), fallback.font_scale, float),
        window=_text(node.find("window")),
    )


def parse_document(root: ET.Element, path: str = DEFAULT_CONFIG_PATH) -> Document:
    if root.tag != "tripCalendar":
        raise ConfigError(f"root element must be <tripCalendar>, got <{root.tag}>")

    settings = parse_settings(root)

    entries: dict[date, str] = {}
    days_node = root.find("days")
    if days_node is not None:
        for day_node in days_node.findall("day"):
            raw = day_node.get("date", "")
            if not raw:
                continue
            when = _parse_date(raw, "day/@date")
            text = (day_node.text or "").strip("\n")
            if text.strip():
                entries[when] = text

    calendar = TripCalendar(
        start=settings.start_week,
        end=settings.end_week,
        first_day=settings.first_day,
        entries=entries,
    )
    calendar.grow_to_fit()  # never hide text that is outside the saved range

    history: list[Change] = []
    history_node = root.find("history")
    if history_node is not None:
        for change_node in history_node.findall("change"):
            history.append(
                Change(
                    revision=_parse_number(change_node.get("revision", "0"), 0, int),
                    at=change_node.get("at", ""),
                    version=change_node.get("version", ""),
                    summary=(change_node.text or "").strip(),
                )
            )

    return Document(
        settings=settings,
        calendar=calendar,
        revision=_parse_number(root.get("revision", "0"), 0, int),
        saved_at=root.get("savedAt", ""),
        app_version=root.get("appVersion", ""),
        history=history[-HISTORY_LIMIT:],
        path=path,
    )


def load(path: str = DEFAULT_CONFIG_PATH) -> Document:
    """Load ``path``, or hand back a fresh four-week calendar if it is absent."""
    if not os.path.exists(path):
        return new_document(path)
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        raise ConfigError(f"{path} is not valid XML: {exc}") from exc
    return parse_document(root, path)


def new_document(path: str = DEFAULT_CONFIG_PATH) -> Document:
    settings = _default_settings()
    calendar = TripCalendar(
        start=settings.start_week, end=settings.end_week, first_day=settings.first_day
    )
    return Document(settings=settings, calendar=calendar, path=path)


# -------------------------------------------------------------------- write


def build_tree(doc: Document) -> ET.ElementTree:
    doc.sync_settings_from_calendar()
    settings = doc.settings

    root = ET.Element(
        "tripCalendar",
        {
            "schemaVersion": str(SCHEMA_VERSION),
            "appVersion": __version__,
            "revision": str(doc.revision),
            "savedAt": doc.saved_at or utc_now_iso(),
        },
    )

    node = ET.SubElement(root, "settings")
    for tag, value in (
        ("startWeek", settings.start_week.isoformat()),
        ("endWeek", settings.end_week.isoformat()),
        ("firstDayOfWeek", settings.first_day),
        ("title", settings.title),
        ("theme", settings.theme),
        ("dateFormat", settings.date_format),
        ("cellWidth", str(settings.cell_width)),
        ("cellHeight", str(settings.cell_height)),
        ("fontScale", f"{settings.font_scale:g}"),
        ("window", settings.window),
    ):
        ET.SubElement(node, tag).text = value

    days_node = ET.SubElement(root, "days")
    for when in sorted(doc.calendar.entries):
        text = doc.calendar.entries[when]
        if not text.strip():
            continue
        ET.SubElement(days_node, "day", {"date": when.isoformat()}).text = text

    history_node = ET.SubElement(root, "history")
    for change in doc.history[-HISTORY_LIMIT:]:
        ET.SubElement(
            history_node,
            "change",
            {
                "revision": str(change.revision),
                "at": change.at,
                "version": change.version,
            },
        ).text = change.summary

    ET.indent(root, space="  ")
    return ET.ElementTree(root)


def save(doc: Document, path: str | None = None) -> str:
    """Write the document, stamping it with the current version and time.

    The file is written to a sibling temporary file and then moved into place so
    an interrupted save can never leave a half-written plan behind.
    """
    target = path or doc.path or DEFAULT_CONFIG_PATH
    doc.saved_at = utc_now_iso()
    doc.app_version = __version__
    tree = build_tree(doc)

    directory = os.path.dirname(os.path.abspath(target))
    os.makedirs(directory, exist_ok=True)
    tmp = f"{target}.tmp"
    tree.write(tmp, encoding="utf-8", xml_declaration=True)
    os.replace(tmp, target)
    doc.path = target
    return target
