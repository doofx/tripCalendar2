"""Fold the calendar into a one-line-per-day summary, short enough to text.

The grid holds several lines per day. A message wants one, so each day is
reduced to its opening lines joined together:

    day 1 - Flight to Dubrovnik + tour
    day 2 - Kravica waterfall + Mostar

The first two lines of a day are what carry the plan — where you are going and
what you are doing — while the lines below them tend to be logistics. So the
opening lines are kept and the rest dropped, with lines that are purely
housekeeping ("Sleep: Kyoto") passed over rather than spent as one of the two.
Day numbers count from the first day that has anything written on it, so day 1
is the first day of the trip rather than the first cell in the grid.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from .config import Document

#: Lines that are housekeeping rather than plan, skipped when picking the
#: opening lines. Matched at the start of a line, ignoring case.
DEFAULT_SKIP = ("sleep:",)


@dataclass
class MessageStyle:
    """How much of each day to keep, and how to join it up."""

    lines: int = 2
    separator: str = " + "
    day_label: str = "day"
    skip_prefixes: tuple[str, ...] = DEFAULT_SKIP
    include_header: bool = True
    #: Kept for callers that want dates instead of, or beside, day numbers.
    show_dates: bool = False
    date_format: str = ""

    def normalised(self) -> "MessageStyle":
        return MessageStyle(
            lines=max(1, int(self.lines)),
            separator=self.separator,
            day_label=self.day_label,
            skip_prefixes=tuple(p.lower() for p in self.skip_prefixes if p.strip()),
            include_header=self.include_header,
            show_dates=self.show_dates,
            date_format=self.date_format,
        )


def _is_housekeeping(line: str, prefixes: tuple[str, ...]) -> bool:
    lowered = line.lower()
    return any(lowered.startswith(prefix) for prefix in prefixes)


def summarise_day(text: str, style: MessageStyle | None = None) -> str:
    """Reduce one day's text to a single line.

    Blank lines are ignored, housekeeping lines are passed over, and the first
    ``style.lines`` remaining lines are joined. A day that is nothing but
    housekeeping falls back to its first line rather than vanishing.
    """
    style = (style or MessageStyle()).normalised()
    if not text.strip():
        return ""

    present = [line.strip() for line in text.splitlines() if line.strip()]
    kept: list[str] = []
    for line in present:
        if _is_housekeeping(line, style.skip_prefixes):
            continue
        kept.append(line)
        if len(kept) >= style.lines:
            break

    if not kept:  # the whole day was housekeeping; better that than nothing
        kept = present[: style.lines]
    return style.separator.join(kept)


def render(doc: Document, style: MessageStyle | None = None) -> str:
    """Build the whole message: an optional title line, then one line per day."""
    style = (style or MessageStyle()).normalised()
    cal = doc.calendar
    date_format = style.date_format or doc.settings.date_format

    written = sorted(day for day in cal.entries if cal.entries[day].strip())
    lines: list[str] = []

    if style.include_header and doc.settings.title:
        if written:
            span = (
                f"{written[0].strftime(date_format)}"
                f"–{written[-1].strftime(date_format)}"
            )
            lines.append(f"{doc.settings.title} ({span})")
        else:
            lines.append(doc.settings.title)

    if not written:
        return "\n".join(lines)

    first = written[0]
    for day in written:
        summary = summarise_day(cal.get(day), style)
        if not summary:
            continue
        number = (day - first).days + 1
        label = f"{style.day_label} {number}".strip()
        if style.show_dates:
            label = f"{label} ({day.strftime(date_format)})"
        lines.append(f"{label} - {summary}")

    return "\n".join(lines)


def save(doc: Document, path: str, style: MessageStyle | None = None) -> str:
    """Write the message to a UTF-8 text file and return the path written."""
    text = render(doc, style)
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text + "\n")
    return os.path.abspath(path)


def day_count(doc: Document) -> int:
    """How many days the message will cover, for a preview line."""
    written = sorted(day for day in doc.calendar.entries if doc.calendar.entries[day].strip())
    if not written:
        return 0
    return (written[-1] - written[0]).days + 1
