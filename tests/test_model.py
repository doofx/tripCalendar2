"""Tests for the calendar model — grid geometry and the day-shift operations."""

from __future__ import annotations

import os
import sys
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tripcalendar.model import (  # noqa: E402
    MONDAY,
    SUNDAY,
    ShiftConflict,
    TripCalendar,
    week_end,
    week_start,
)

D = date.fromisoformat


def build(start="2023-02-26", end="2023-03-25", **entries) -> TripCalendar:
    return TripCalendar(
        start=D(start),
        end=D(end),
        entries={D(k.replace("_", "-").lstrip("d")): v for k, v in entries.items()},
    )


class WeekBoundaries(unittest.TestCase):
    def test_sunday_start_snaps_backwards(self):
        # 2023-03-01 is a Wednesday; its Sunday is 2023-02-26.
        self.assertEqual(week_start(D("2023-03-01")), D("2023-02-26"))
        self.assertEqual(week_end(D("2023-03-01")), D("2023-03-04"))

    def test_sunday_is_its_own_week_start(self):
        self.assertEqual(week_start(D("2023-02-26")), D("2023-02-26"))

    def test_monday_start_is_supported(self):
        self.assertEqual(week_start(D("2023-03-01"), MONDAY), D("2023-02-27"))
        self.assertEqual(week_end(D("2023-03-01"), MONDAY), D("2023-03-05"))

    def test_range_is_normalised_to_whole_weeks(self):
        cal = TripCalendar(start=D("2023-03-01"), end=D("2023-03-08"))
        self.assertEqual(cal.start, D("2023-02-26"))
        self.assertEqual(cal.end, D("2023-03-11"))
        self.assertEqual(cal.week_count, 2)
        self.assertEqual(cal.day_count, 14)


class Grid(unittest.TestCase):
    def test_weeks_are_rows_of_seven_left_to_right(self):
        cal = build()
        weeks = cal.weeks()
        self.assertEqual(len(weeks), 4)
        self.assertTrue(all(len(week) == 7 for week in weeks))
        self.assertEqual(weeks[0][0], D("2023-02-26"))
        self.assertEqual(weeks[0][6], D("2023-03-04"))
        self.assertEqual(weeks[1][0], D("2023-03-05"))

    def test_first_column_is_sunday(self):
        cal = build()
        for week in cal.weeks():
            self.assertEqual(week[0].strftime("%a"), "Sun")

    def test_switching_week_start_keeps_every_written_day_visible(self):
        cal = build()
        cal.set(D("2023-02-26"), "first day")
        cal.set_first_day(MONDAY)
        self.assertEqual(cal.first_day, MONDAY)
        self.assertTrue(cal.contains(D("2023-02-26")))
        for week in cal.weeks():
            self.assertEqual(week[0].strftime("%a"), "Mon")


class ForwardShift(unittest.TestCase):
    def setUp(self):
        self.cal = build()
        self.cal.set(D("2023-03-01"), "Tokyo")
        self.cal.set(D("2023-03-02"), "Osaka")
        self.cal.set(D("2023-03-03"), "Kyoto")

    def test_anchor_and_later_days_move_one_day_later(self):
        result = self.cal.shift_forward(D("2023-03-02"))
        self.assertEqual(self.cal.get(D("2023-03-01")), "Tokyo")  # untouched
        self.assertEqual(self.cal.get(D("2023-03-02")), "")       # now a spare day
        self.assertEqual(self.cal.get(D("2023-03-03")), "Osaka")
        self.assertEqual(self.cal.get(D("2023-03-04")), "Kyoto")
        self.assertEqual(result.weeks_added, 0)

    def test_shifting_from_the_first_day_moves_everything(self):
        self.cal.shift_forward(self.cal.start)
        self.assertEqual(self.cal.get(D("2023-03-02")), "Tokyo")
        self.assertEqual(self.cal.get(D("2023-03-04")), "Kyoto")

    def test_a_week_is_added_rather_than_losing_the_last_day(self):
        last = self.cal.end
        self.cal.set(last, "Flight home")
        result = self.cal.shift_forward(D("2023-03-02"))
        self.assertEqual(result.weeks_added, 1)
        self.assertEqual(self.cal.end, last + timedelta(days=7))
        self.assertEqual(self.cal.get(last + timedelta(days=1)), "Flight home")
        self.assertEqual(self.cal.week_count, 5)

    def test_nothing_is_ever_dropped(self):
        before = sorted(self.cal.entries.values())
        self.cal.shift_forward(D("2023-03-01"))
        self.assertEqual(sorted(self.cal.entries.values()), before)

    def test_shift_past_the_end_of_an_empty_tail_adds_no_weeks(self):
        result = self.cal.shift_forward(D("2023-03-20"))
        self.assertEqual(result.weeks_added, 0)
        self.assertEqual(self.cal.week_count, 4)


class BackwardShift(unittest.TestCase):
    def setUp(self):
        self.cal = build()
        self.cal.set(D("2023-03-02"), "Osaka")
        self.cal.set(D("2023-03-03"), "Kyoto")

    def test_anchor_and_later_days_move_one_day_earlier(self):
        result = self.cal.shift_backward(D("2023-03-02"))
        self.assertEqual(self.cal.get(D("2023-03-01")), "Osaka")
        self.assertEqual(self.cal.get(D("2023-03-02")), "Kyoto")
        self.assertEqual(self.cal.get(D("2023-03-03")), "")
        self.assertEqual(result.weeks_added, 0)

    def test_it_refuses_to_silently_overwrite_the_preceding_day(self):
        self.cal.set(D("2023-03-01"), "Tokyo")
        with self.assertRaises(ShiftConflict) as caught:
            self.cal.shift_backward(D("2023-03-02"))
        self.assertEqual(caught.exception.victim, D("2023-03-01"))
        self.assertEqual(caught.exception.text, "Tokyo")
        # The refused shift must leave the calendar exactly as it was.
        self.assertEqual(self.cal.get(D("2023-03-01")), "Tokyo")
        self.assertEqual(self.cal.get(D("2023-03-02")), "Osaka")

    def test_forcing_the_shift_overwrites_and_says_so(self):
        self.cal.set(D("2023-03-01"), "Tokyo")
        result = self.cal.shift_backward(D("2023-03-02"), force=True)
        self.assertEqual(result.overwritten, "Tokyo")
        self.assertEqual(self.cal.get(D("2023-03-01")), "Osaka")

    def test_a_week_is_added_at_the_start_when_there_is_no_room(self):
        start = self.cal.start
        self.cal.set(start, "Pack")
        result = self.cal.shift_backward(start)
        self.assertEqual(result.weeks_added, 1)
        self.assertTrue(result.added_at_start)
        self.assertEqual(self.cal.start, start - timedelta(days=7))
        self.assertEqual(self.cal.get(start - timedelta(days=1)), "Pack")

    def test_a_refused_shift_at_the_start_does_not_leave_a_stray_week(self):
        start = self.cal.start
        self.cal.set(start, "Pack")
        self.cal.set(start - timedelta(days=1), "Should be unreachable")
        self.cal.grow_to_fit()
        weeks = self.cal.week_count
        with self.assertRaises(ShiftConflict):
            self.cal.shift_backward(start)
        self.assertEqual(self.cal.week_count, weeks)

    def test_round_trip_forward_then_backward_restores_the_plan(self):
        before = dict(self.cal.entries)
        self.cal.shift_forward(D("2023-03-02"))
        self.cal.shift_backward(D("2023-03-03"))
        self.assertEqual(self.cal.entries, before)


class RangeGrowth(unittest.TestCase):
    def test_grow_to_fit_covers_text_outside_the_range(self):
        cal = build()
        cal.entries[D("2023-04-10")] = "late addition"
        added = cal.grow_to_fit()
        self.assertGreater(added, 0)
        self.assertTrue(cal.contains(D("2023-04-10")))

    def test_trim_removes_blank_weeks_from_both_ends(self):
        cal = build(start="2023-02-26", end="2023-04-01")
        cal.set(D("2023-03-08"), "the only plan")
        removed = cal.trim_empty_weeks()
        self.assertEqual(removed, 4)  # one week before, three after
        self.assertEqual(cal.week_count, 1)
        self.assertTrue(cal.contains(D("2023-03-08")))

    def test_trim_always_leaves_one_week(self):
        cal = build()
        cal.trim_empty_weeks()
        self.assertEqual(cal.week_count, 1)


class TextStorage(unittest.TestCase):
    def test_blank_text_clears_the_day(self):
        cal = build()
        cal.set(D("2023-03-01"), "something")
        cal.set(D("2023-03-01"), "   \n  ")
        self.assertNotIn(D("2023-03-01"), cal.entries)
        self.assertFalse(cal.has_text(D("2023-03-01")))

    def test_peek_reports_what_a_backward_shift_would_destroy(self):
        cal = build()
        cal.set(D("2023-03-01"), "Tokyo")
        self.assertEqual(cal.peek_backward_victim(D("2023-03-02")), "Tokyo")
        self.assertIsNone(cal.peek_backward_victim(D("2023-03-05")))
        self.assertIsNone(cal.peek_backward_victim(cal.start))


if __name__ == "__main__":
    unittest.main()
