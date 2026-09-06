"""Tests for the one-line-per-day text message summary."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tripcalendar import config, message  # noqa: E402
from tripcalendar.model import TripCalendar  # noqa: E402

D = date.fromisoformat


def plan(title: str = "", **days: str) -> config.Document:
    """Build a document from d0=..., d1=... offsets into the first week."""
    start = D("2023-02-26")
    calendar = TripCalendar(start=start, end=start + timedelta(days=27))
    for key, text in days.items():
        calendar.set(start + timedelta(days=int(key.lstrip("d"))), text)
    settings = config.Settings(
        start_week=calendar.start, end_week=calendar.end, title=title
    )
    return config.Document(settings=settings, calendar=calendar)


class TheRequestedFormat(unittest.TestCase):
    def test_it_produces_the_shape_that_was_asked_for(self):
        doc = plan(
            d0="Flight to Dubrovnik\ntour",
            d1="Kravica waterfall\nMostar",
        )
        self.assertEqual(
            message.render(doc),
            "day 1 - Flight to Dubrovnik + tour\nday 2 - Kravica waterfall + Mostar",
        )

    def test_the_first_two_lines_become_one(self):
        self.assertEqual(
            message.summarise_day("Kyoto temples\nInari festival\nand more\nSleep: Kyoto"),
            "Kyoto temples + Inari festival",
        )

    def test_a_single_line_day_stays_as_it_is(self):
        self.assertEqual(message.summarise_day("Alpine route"), "Alpine route")


class HousekeepingLines(unittest.TestCase):
    def test_a_sleep_line_is_not_spent_as_one_of_the_two(self):
        self.assertEqual(message.summarise_day("Osaka\nSleep: Osaka"), "Osaka")

    def test_it_is_skipped_wherever_it_appears(self):
        self.assertEqual(
            message.summarise_day("Kyoto\nSleep: Kyoto\nArashiyama"),
            "Kyoto + Arashiyama",
        )

    def test_matching_ignores_case(self):
        self.assertEqual(message.summarise_day("Osaka\nsleep: Osaka"), "Osaka")

    def test_a_day_that_is_only_housekeeping_still_says_something(self):
        # Better a slightly odd line than a day silently missing from the trip.
        self.assertEqual(message.summarise_day("Sleep: Tokyo"), "Sleep: Tokyo")

    def test_the_skipped_prefixes_can_be_changed(self):
        style = message.MessageStyle(skip_prefixes=("hotel:",))
        self.assertEqual(
            message.summarise_day("Rome\nHotel: Trastevere\nColosseum", style),
            "Rome + Colosseum",
        )


class Whitespace(unittest.TestCase):
    def test_blank_lines_inside_a_day_are_ignored(self):
        self.assertEqual(message.summarise_day("Rome\n\n\nVatican"), "Rome + Vatican")

    def test_surrounding_spaces_are_trimmed(self):
        self.assertEqual(message.summarise_day("  Rome  \n   Vatican  "), "Rome + Vatican")

    def test_an_empty_day_summarises_to_nothing(self):
        self.assertEqual(message.summarise_day("   \n  "), "")


class DayNumbering(unittest.TestCase):
    def test_day_one_is_the_first_day_with_anything_written_on_it(self):
        # The grid starts on 26 February; the trip starts on the 28th.
        doc = plan(d2="Fly out", d3="Arrive")
        self.assertEqual(
            message.render(doc), "day 1 - Fly out\nday 2 - Arrive"
        )

    def test_blank_days_are_left_out_but_still_counted(self):
        doc = plan(d0="Fly out", d3="Arrive")
        self.assertEqual(message.render(doc), "day 1 - Fly out\nday 4 - Arrive")

    def test_an_empty_calendar_produces_nothing(self):
        self.assertEqual(message.render(plan()), "")

    def test_day_count_spans_the_written_trip(self):
        self.assertEqual(message.day_count(plan(d0="a", d3="b")), 4)
        self.assertEqual(message.day_count(plan()), 0)


class Options(unittest.TestCase):
    def setUp(self):
        self.doc = plan("Croatia", d0="Dubrovnik\ntour\nextra", d1="Mostar\nKravica")

    def test_one_line_per_day_keeps_only_the_first(self):
        style = message.MessageStyle(lines=1)
        self.assertEqual(
            message.render(self.doc, style), "Croatia (26/02/2023–27/02/2023)\n"
            "day 1 - Dubrovnik\nday 2 - Mostar"
        )

    def test_three_lines_per_day_keeps_more(self):
        style = message.MessageStyle(lines=3, include_header=False)
        self.assertEqual(
            message.render(self.doc, style),
            "day 1 - Dubrovnik + tour + extra\nday 2 - Mostar + Kravica",
        )

    def test_a_zero_or_negative_line_count_still_gives_one_line(self):
        style = message.MessageStyle(lines=0, include_header=False)
        self.assertEqual(
            message.render(self.doc, style), "day 1 - Dubrovnik\nday 2 - Mostar"
        )

    def test_the_title_line_carries_the_span_of_the_trip(self):
        self.assertTrue(
            message.render(self.doc).startswith("Croatia (26/02/2023–27/02/2023)")
        )

    def test_the_title_line_can_be_left_off(self):
        style = message.MessageStyle(include_header=False)
        self.assertFalse(message.render(self.doc, style).startswith("Croatia"))

    def test_an_untitled_plan_has_no_title_line(self):
        doc = plan(d0="Dubrovnik")
        self.assertEqual(message.render(doc), "day 1 - Dubrovnik")

    def test_dates_can_be_shown_beside_the_day_number(self):
        style = message.MessageStyle(show_dates=True, include_header=False)
        self.assertEqual(
            message.render(self.doc, style).splitlines()[0],
            "day 1 (26/02/2023) - Dubrovnik + tour",
        )

    def test_the_separator_can_be_changed(self):
        style = message.MessageStyle(separator=", ", include_header=False)
        self.assertEqual(
            message.render(self.doc, style).splitlines()[0], "day 1 - Dubrovnik, tour"
        )

    def test_the_day_label_can_be_changed(self):
        style = message.MessageStyle(day_label="Day", include_header=False)
        self.assertTrue(message.render(self.doc, style).startswith("Day 1 - "))


class SavingToAFile(unittest.TestCase):
    def test_it_writes_utf8_text_ending_in_a_newline(self):
        doc = plan("Croatia", d0="Dubrovnik\ntour")
        with tempfile.TemporaryDirectory() as tmp:
            written = message.save(doc, os.path.join(tmp, "trip.txt"))
            self.assertTrue(os.path.isabs(written))
            with open(written, encoding="utf-8") as handle:
                body = handle.read()
        self.assertTrue(body.endswith("\n"))
        self.assertIn("day 1 - Dubrovnik + tour", body)


class TheShippedExample(unittest.TestCase):
    def test_the_sample_trip_summarises_cleanly(self):
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        doc = config.load(os.path.join(here, "config", "example_trip.xml"))
        lines = message.render(doc).splitlines()

        self.assertEqual(lines[0], "Japan, Spring 2023 (28/02/2023–25/03/2023)")
        self.assertEqual(lines[1], "day 1 - Flight to Tokyo at 20:00")
        self.assertEqual(lines[4], "day 4 - Osaka")  # "Sleep: Osaka" left out
        self.assertEqual(len(lines), 27)  # a title line and 26 written days
        self.assertTrue(all("Sleep:" not in line for line in lines[1:]))


if __name__ == "__main__":
    unittest.main()
