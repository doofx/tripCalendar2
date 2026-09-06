"""Backward compatibility with XML files written by earlier versions.

The rule these tests enforce is simple: opening and saving someone's existing
file must never lose anything from it, including parts this version does not
understand.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tripcalendar import config  # noqa: E402
from tripcalendar.version import SCHEMA_VERSION  # noqa: E402

D = date.fromisoformat

# A 1.0.0/1.0.1 file, which kept the window position inside the plan, plus
# material that only a later version would write.
LEGACY = """<?xml version="1.0" encoding="utf-8"?>
<tripCalendar schemaVersion="1" appVersion="1.0.0" revision="3"
              savedAt="2026-01-02T03:04:05+00:00" customAttr="keep me">
  <settings>
    <startWeek>2023-02-26</startWeek>
    <endWeek>2023-03-25</endWeek>
    <firstDayOfWeek>sunday</firstDayOfWeek>
    <title>Japan</title>
    <theme>midnight</theme>
    <dateFormat>%d/%m/%Y</dateFormat>
    <cellWidth>168</cellWidth>
    <cellHeight>132</cellHeight>
    <fontScale>1</fontScale>
    <window>1360x880+120+60</window>
    <somethingNewer>hello</somethingNewer>
  </settings>
  <days>
    <day date="2023-03-01">Tokyo
Sleep: Tokyo</day>
  </days>
  <history>
    <change revision="3" at="2026-01-02T03:04:05+00:00" version="1.0.0">old edit</change>
  </history>
  <futureSection><thing a="1">payload</thing></futureSection>
</tripCalendar>
"""


def round_trip(xml: str) -> str:
    doc = config.parse_document(ET.fromstring(xml))
    with tempfile.TemporaryDirectory() as tmp:
        target = os.path.join(tmp, "out.xml")
        config.save(doc, target)
        with open(target, encoding="utf-8") as handle:
            return handle.read()


class OldFilesStillOpen(unittest.TestCase):
    def setUp(self):
        self.doc = config.parse_document(ET.fromstring(LEGACY))

    def test_the_plan_itself_reads_normally(self):
        self.assertEqual(self.doc.settings.title, "Japan")
        self.assertEqual(self.doc.settings.theme, "midnight")
        self.assertEqual(self.doc.calendar.get(D("2023-03-01")), "Tokyo\nSleep: Tokyo")
        self.assertEqual(self.doc.revision, 3)

    def test_a_window_position_from_an_older_version_is_still_readable(self):
        # 1.0.2 moved this to app_state.xml; an upgrading user keeps their window.
        self.assertEqual(self.doc.settings.extra["window"], "1360x880+120+60")

    def test_settings_from_another_version_are_kept(self):
        self.assertEqual(self.doc.settings.extra["somethingNewer"], "hello")

    def test_whole_sections_from_another_version_are_kept(self):
        self.assertEqual([node.tag for node in self.doc.extra_sections], ["futureSection"])

    def test_root_attributes_from_another_version_are_kept(self):
        self.assertEqual(self.doc.extra_root_attrs, {"customAttr": "keep me"})


class SavingLosesNothing(unittest.TestCase):
    def setUp(self):
        self.written = round_trip(LEGACY)

    def test_unknown_settings_survive(self):
        self.assertIn("<window>1360x880+120+60</window>", self.written)
        self.assertIn("<somethingNewer>hello</somethingNewer>", self.written)

    def test_unknown_sections_survive_intact(self):
        self.assertIn("<futureSection>", self.written)
        self.assertIn('<thing a="1">payload</thing>', self.written)

    def test_unknown_root_attributes_survive(self):
        self.assertIn('customAttr="keep me"', self.written)

    def test_known_content_is_still_written(self):
        self.assertIn("<title>Japan</title>", self.written)
        self.assertIn('<day date="2023-03-01">', self.written)
        self.assertIn("old edit", self.written)

    def test_a_second_round_trip_is_stable(self):
        again = round_trip(self.written)
        # Only the save stamp may differ, so compare everything else.
        strip = lambda text: "\n".join(  # noqa: E731
            line for line in text.splitlines() if "savedAt" not in line
        )
        self.assertEqual(strip(again), strip(self.written))


class DamagedOrPartialFiles(unittest.TestCase):
    def test_a_missing_settings_section_falls_back_to_defaults(self):
        doc = config.parse_document(
            ET.fromstring('<tripCalendar><days><day date="2023-03-01">x</day></days></tripCalendar>')
        )
        self.assertTrue(doc.calendar.contains(D("2023-03-01")))
        self.assertEqual(doc.settings.first_day, "sunday")

    def test_one_unreadable_day_does_not_cost_the_whole_plan(self):
        xml = LEGACY.replace(
            "  </days>", '    <day date="tuesday-ish">rubbish</day>\n  </days>'
        )
        doc = config.parse_document(ET.fromstring(xml))
        self.assertEqual(doc.calendar.get(D("2023-03-01")), "Tokyo\nSleep: Tokyo")
        self.assertEqual(len(doc.warnings), 1)
        self.assertIn("tuesday-ish", doc.warnings[0])

    def test_a_file_from_a_newer_schema_loads_with_a_warning(self):
        xml = LEGACY.replace('schemaVersion="1"', f'schemaVersion="{SCHEMA_VERSION + 5}"')
        doc = config.parse_document(ET.fromstring(xml))
        self.assertEqual(doc.settings.title, "Japan")
        self.assertTrue(any("newer version" in w for w in doc.warnings))

    def test_a_clean_file_produces_no_warnings(self):
        self.assertEqual(config.parse_document(ET.fromstring(LEGACY)).warnings, [])

    def test_a_foreign_root_element_is_still_rejected(self):
        with self.assertRaises(config.ConfigError):
            config.parse_document(ET.fromstring("<calendar><days/></calendar>"))


class PreservedMaterialIsNotEditedContent(unittest.TestCase):
    def test_unknown_settings_do_not_make_the_plan_look_unsaved(self):
        doc = config.parse_document(ET.fromstring(LEGACY))
        before = config.fingerprint(doc)
        doc.settings.extra["yetAnother"] = "value"
        self.assertEqual(config.fingerprint(doc), before)


if __name__ == "__main__":
    unittest.main()
