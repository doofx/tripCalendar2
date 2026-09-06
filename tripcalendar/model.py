"""Trip calendar data model.

The calendar is a contiguous run of whole weeks. Every displayed week starts on
the configured first day of the week (Sunday by default) and runs left to right,
so the grid is always a clean rectangle of 7 columns by N rows.

Day text lives in :attr:`TripCalendar.entries`, keyed by date. Days with no text
simply have no key, which keeps the shift operations cheap and makes an empty
day and a day of whitespace indistinguishable, as they should be.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Iterator

DAY = timedelta(days=1)
WEEK = timedelta(days=7)

SUNDAY = "sunday"
MONDAY = "monday"

#: Column headers, in display order, for each supported week start.
WEEKDAY_HEADERS = {
    SUNDAY: ("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"),
    MONDAY: ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"),
}


class ShiftConflict(Exception):
    """Raised when shifting backward would overwrite text the user still has.

    The UI catches this, shows what is about to be lost, and re-runs the shift
    with ``force=True`` if the user confirms.
    """

    def __init__(self, victim: date, text: str) -> None:
        super().__init__(f"{victim.isoformat()} already has text")
        self.victim = victim
        self.text = text


@dataclass
class ShiftResult:
    """What a shift actually did, so the UI can report and rebuild."""

    anchor: date
    direction: int  # +1 forward (later), -1 backward (earlier)
    weeks_added: int = 0
    added_at_start: bool = False
    overwritten: str | None = None

    @property
    def summary(self) -> str:
        way = "forward" if self.direction > 0 else "backward"
        parts = [f"Moved {self.anchor.isoformat()} and later one day {way}"]
        if self.weeks_added:
            where = "before the start" if self.added_at_start else "at the end"
            week_word = "week" if self.weeks_added == 1 else "weeks"
            parts.append(f"added {self.weeks_added} {week_word} {where}")
        if self.overwritten:
            parts.append("overwrote text on the preceding day")
        return "; ".join(parts)


def week_start(day: date, first_day: str = SUNDAY) -> date:
    """Snap ``day`` back to the first day of the week containing it."""
    if first_day == MONDAY:
        offset = day.weekday()  # Mon=0 .. Sun=6
    else:
        offset = (day.weekday() + 1) % 7  # Sun=0 .. Sat=6
    return day - timedelta(days=offset)


def week_end(day: date, first_day: str = SUNDAY) -> date:
    return week_start(day, first_day) + timedelta(days=6)


@dataclass
class TripCalendar:
    """A whole number of weeks of trip plan, plus the text on each day."""

    start: date
    end: date
    first_day: str = SUNDAY
    entries: dict[date, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.first_day not in WEEKDAY_HEADERS:
            self.first_day = SUNDAY
        self.normalise()

    # ---------------------------------------------------------------- range

    def normalise(self) -> None:
        """Force the range onto whole-week boundaries, smallest sane window."""
        self.start = week_start(self.start, self.first_day)
        self.end = week_end(max(self.end, self.start), self.first_day)

    def set_first_day(self, first_day: str) -> None:
        """Change the week start, keeping every existing day inside the range."""
        if first_day not in WEEKDAY_HEADERS or first_day == self.first_day:
            return
        self.first_day = first_day
        self.normalise()
        self.grow_to_fit()

    @property
    def week_count(self) -> int:
        return ((self.end - self.start).days + 1) // 7

    @property
    def day_count(self) -> int:
        return (self.end - self.start).days + 1

    def days(self) -> Iterator[date]:
        day = self.start
        while day <= self.end:
            yield day
            day += DAY

    def weeks(self) -> list[list[date]]:
        """The grid: one list of 7 dates per displayed row."""
        return [
            [self.start + timedelta(days=w * 7 + i) for i in range(7)]
            for w in range(self.week_count)
        ]

    def contains(self, day: date) -> bool:
        return self.start <= day <= self.end

    def append_week(self, count: int = 1) -> int:
        self.end += WEEK * count
        return count

    def prepend_week(self, count: int = 1) -> int:
        self.start -= WEEK * count
        return count

    def grow_to_fit(self) -> int:
        """Extend the range until every entry with text is inside it."""
        written = [d for d, text in self.entries.items() if text.strip()]
        if not written:
            return 0
        added = 0
        while min(written) < self.start:
            self.prepend_week()
            added += 1
        while max(written) > self.end:
            self.append_week()
            added += 1
        return added

    def trim_empty_weeks(self) -> int:
        """Drop blank weeks from both ends, always leaving at least one week."""
        removed = 0
        while self.week_count > 1 and not self._week_has_text(self.start):
            self.start += WEEK
            removed += 1
        while self.week_count > 1 and not self._week_has_text(self.end - timedelta(days=6)):
            self.end -= WEEK
            removed += 1
        return removed

    def _week_has_text(self, first: date) -> bool:
        return any(
            self.entries.get(first + timedelta(days=i), "").strip() for i in range(7)
        )

    # ---------------------------------------------------------------- text

    def get(self, day: date) -> str:
        return self.entries.get(day, "")

    def set(self, day: date, text: str) -> None:
        if text.strip():
            self.entries[day] = text
        else:
            self.entries.pop(day, None)

    def clear(self, day: date) -> None:
        self.entries.pop(day, None)

    def has_text(self, day: date) -> bool:
        return bool(self.entries.get(day, "").strip())

    # -------------------------------------------------------------- shifts

    def _tail(self, anchor: date) -> list[date]:
        return sorted(d for d in self.entries if d >= anchor)

    def shift_forward(self, anchor: date) -> ShiftResult:
        """Move ``anchor`` and every later day one day later.

        The anchor day is left blank, which is the point: it inserts a spare day
        into the plan. If the last written day would fall off the end of the
        displayed range, weeks are appended so nothing is ever dropped.
        """
        tail = self._tail(anchor)
        result = ShiftResult(anchor=anchor, direction=+1)
        if tail:
            needed = tail[-1] + DAY
            while needed > self.end:
                self.append_week()
                result.weeks_added += 1
        for day in reversed(tail):  # highest first, so the target is always free
            self.entries[day + DAY] = self.entries.pop(day)
        return result

    def shift_backward(self, anchor: date, force: bool = False) -> ShiftResult:
        """Move ``anchor`` and every later day one day earlier.

        This closes the gap ahead of the anchor. If the day before the anchor
        already has text that text is destroyed, so the caller is asked to
        confirm first via :class:`ShiftConflict`. When the anchor is the very
        first day on display a week is prepended to make room for it.
        """
        result = ShiftResult(anchor=anchor, direction=-1)
        if anchor <= self.start:
            self.prepend_week()
            result.weeks_added = 1
            result.added_at_start = True

        victim = anchor - DAY
        existing = self.entries.get(victim, "")
        if existing.strip():
            if not force:
                if result.weeks_added:  # undo the speculative growth
                    self.start += WEEK
                raise ShiftConflict(victim, existing)
            result.overwritten = existing

        self.entries.pop(victim, None)
        for day in self._tail(anchor):  # lowest first, so the target is always free
            self.entries[day - DAY] = self.entries.pop(day)
        return result

    def peek_backward_victim(self, anchor: date) -> str | None:
        """Text that a backward shift from ``anchor`` would destroy, if any."""
        if anchor <= self.start:
            return None
        text = self.entries.get(anchor - DAY, "")
        return text if text.strip() else None
