"""Tests for XML persistence: settings, day text, and the change history."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tripcalendar import config  # noqa: E402
from tripcalendar.model import MONDAY, SUNDAY  # noqa: E402
from tripcalendar.version import SCHEMA_VERSION, __version__  # noqa: E402

D = date.fromisoformat

SAMPLE = """<?xml version="1.0" encoding="utf-8"?>
<tripCalendar schemaVersion="1" appVersion="0.9.0" revision="4" savedAt="2026-01-02T03:04:05+00:00">
  <settings>
    <startWeek>2023-03-01</startWeek>
    <endWeek>2023-03-15</endWeek>
    <firstDayOfWeek>sunday</firstDayOfWeek>
    <title>Japan</title>
    <theme>midnight</theme>
    <dateFormat>%d/%m/%Y</dateFormat>
  </settings>
  <days>
    <day date="2023-03-02">Osaka
Sleep: Osaka</day>
    <day date="2023-03-03">   </day>
  </days>
  <history>
    <change revision="4" at="2026-01-02T03:04:05+00:00" version="0.9.0">Earlier edit</change>
  </history>
</tripCalendar>
"""


class Loading(unittest.TestCase):
    def parse(self, xml: str = SAMPLE) -> config.Document:
        return config.parse_document(ET.fromstring(xml))

    def test_settings_are_read(self):
        doc = self.parse()
        self.assertEqual(doc.settings.title, "Japan")
        self.assertEqual(doc.settings.theme, "midnight")
        self.assertEqual(doc.settings.first_day, SUNDAY)

    def test_week_bounds_are_snapped_to_whole_weeks(self):
        doc = self.parse()  # 2023-03-01 is a Wednesday, 2023-03-15 a Wednesday
        self.assertEqual(doc.calendar.start, D("2023-02-26"))
        self.assertEqual(doc.calendar.end, D("2023-03-18"))
        self.assertEqual(doc.calendar.week_count, 3)

    def test_day_text_including_newlines_is_preserved(self):
        doc = self.parse()
        self.assertEqual(doc.calendar.get(D("2023-03-02")), "Osaka\nSleep: Osaka")

    def test_whitespace_only_days_are_dropped(self):
        doc = self.parse()
        self.assertNotIn(D("2023-03-03"), doc.calendar.entries)

    def test_revision_and_history_are_read(self):
        doc = self.parse()
        self.assertEqual(doc.revision, 4)
        self.assertEqual(doc.last_change.summary, "Earlier edit")
        self.assertEqual(doc.last_change.version, "0.9.0")

    def test_text_outside_the_saved_range_widens_the_range(self):
        xml = SAMPLE.replace('date="2023-03-02"', 'date="2023-04-20"')
        doc = self.parse(xml)
        self.assertTrue(doc.calendar.contains(D("2023-04-20")))

    def test_an_unknown_week_start_falls_back_to_sunday(self):
        xml = SAMPLE.replace("<firstDayOfWeek>sunday", "<firstDayOfWeek>caturday")
        self.assertEqual(self.parse(xml).settings.first_day, SUNDAY)

    def test_a_wrong_root_element_is_rejected(self):
        with self.assertRaises(config.ConfigError):
            self.parse("<calendar><settings/></calendar>")

    def test_a_bad_date_is_rejected_with_a_useful_message(self):
        xml = SAMPLE.replace("<startWeek>2023-03-01", "<startWeek>March 1st")
        with self.assertRaises(config.ConfigError) as caught:
            self.parse(xml)
        self.assertIn("startWeek", str(caught.exception))

    def test_a_missing_file_yields_a_fresh_four_week_calendar(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc = config.load(os.path.join(tmp, "nope.xml"))
            self.assertEqual(doc.calendar.week_count, 4)
            self.assertEqual(doc.revision, 0)

    def test_broken_xml_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "broken.xml")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("<tripCalendar><settings>")
            with self.assertRaises(config.ConfigError):
                config.load(path)


class Saving(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "trip.xml")
        self.addCleanup(self.tmp.cleanup)

    def test_round_trip_preserves_everything(self):
        doc = config.parse_document(ET.fromstring(SAMPLE), self.path)
        doc.calendar.set(D("2023-03-04"), "Kyoto\nSleep: Kyoto")
        config.save(doc, self.path)

        reloaded = config.load(self.path)
        self.assertEqual(reloaded.settings.title, "Japan")
        self.assertEqual(reloaded.settings.theme, "midnight")
        self.assertEqual(reloaded.calendar.start, doc.calendar.start)
        self.assertEqual(reloaded.calendar.end, doc.calendar.end)
        self.assertEqual(reloaded.calendar.entries, doc.calendar.entries)

    def test_saving_stamps_the_current_version_and_time(self):
        doc = config.parse_document(ET.fromstring(SAMPLE), self.path)
        config.save(doc, self.path)
        root = ET.parse(self.path).getroot()
        self.assertEqual(root.get("appVersion"), __version__)
        self.assertEqual(root.get("schemaVersion"), str(SCHEMA_VERSION))
        self.assertNotEqual(root.get("savedAt"), "2026-01-02T03:04:05+00:00")

    def test_recording_a_change_bumps_the_revision_and_timestamps_it(self):
        doc = config.parse_document(ET.fromstring(SAMPLE), self.path)
        change = doc.record("Moved 2023-03-02 and later one day forward")
        self.assertEqual(change.revision, 5)
        self.assertEqual(doc.revision, 5)
        self.assertEqual(change.version, __version__)
        self.assertTrue(change.at)

        config.save(doc, self.path)
        reloaded = config.load(self.path)
        self.assertEqual(reloaded.revision, 5)
        self.assertEqual(reloaded.last_change.summary, change.summary)

    def test_history_is_capped(self):
        doc = config.parse_document(ET.fromstring(SAMPLE), self.path)
        for index in range(config.HISTORY_LIMIT + 25):
            doc.record(f"change {index}")
        config.save(doc, self.path)
        reloaded = config.load(self.path)
        self.assertEqual(len(reloaded.history), config.HISTORY_LIMIT)
        self.assertEqual(reloaded.last_change.summary, f"change {config.HISTORY_LIMIT + 24}")

    def test_range_changes_are_written_back_to_settings(self):
        doc = config.parse_document(ET.fromstring(SAMPLE), self.path)
        doc.calendar.append_week()
        doc.calendar.set_first_day(MONDAY)
        config.save(doc, self.path)
        reloaded = config.load(self.path)
        self.assertEqual(reloaded.settings.first_day, MONDAY)
        self.assertEqual(reloaded.calendar.end, doc.calendar.end)

    def test_no_temporary_file_is_left_behind(self):
        doc = config.parse_document(ET.fromstring(SAMPLE), self.path)
        config.save(doc, self.path)
        self.assertEqual(os.listdir(self.tmp.name), ["trip.xml"])

    def test_the_shipped_example_loads(self):
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        example = os.path.join(here, "example_trip.xml")
        doc = config.load(example)
        self.assertEqual(doc.calendar.week_count, 5)
        self.assertTrue(doc.calendar.has_text(D("2023-03-01")))


if __name__ == "__main__":
    unittest.main()
