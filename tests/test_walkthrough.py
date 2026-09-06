"""Locks the walkthrough printed in the README, so the docs cannot drift.

Each step below is one numbered step of the "Worked example" section.
"""

from __future__ import annotations

import os
import sys
import unittest
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tripcalendar import config  # noqa: E402

D = date.fromisoformat
EXAMPLE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "example_trip.xml"
)


class ReadmeWalkthrough(unittest.TestCase):
    def setUp(self):
        self.doc = config.load(EXAMPLE)
        self.cal = self.doc.calendar

    def test_the_sample_opens_as_five_weeks_starting_on_a_sunday(self):
        self.assertEqual(self.cal.week_count, 5)
        self.assertEqual(self.cal.start, D("2023-02-26"))
        self.assertEqual(self.cal.start.strftime("%a"), "Sun")
        self.assertEqual(self.cal.end, D("2023-04-01"))

    def test_step_2_trimming_leaves_four_weeks_ending_25_march(self):
        self.assertEqual(self.cal.trim_empty_weeks(), 1)
        self.assertEqual(self.cal.week_count, 4)
        self.assertEqual(self.cal.end, D("2023-03-25"))

    def test_step_3_the_forward_shift_appends_a_fifth_week(self):
        self.cal.trim_empty_weeks()
        arashiyama = self.cal.get(D("2023-03-09"))
        self.assertIn("Arashiyama", arashiyama)

        result = self.cal.shift_forward(D("2023-03-09"))

        self.assertEqual(result.weeks_added, 1)
        self.assertEqual(self.cal.week_count, 5)
        self.assertEqual(self.cal.get(D("2023-03-09")), "")
        self.assertEqual(self.cal.get(D("2023-03-10")), arashiyama)
        # The landing was the last day; it moved on rather than being dropped.
        self.assertEqual(self.cal.get(D("2023-03-26")), "Land at 08:40")
        self.assertIn("added 1 week at the end", result.summary)

    def test_step_4_moving_back_restores_the_plan_exactly(self):
        self.cal.trim_empty_weeks()
        before = dict(self.cal.entries)

        self.cal.shift_forward(D("2023-03-09"))
        self.assertIsNone(self.cal.peek_backward_victim(D("2023-03-10")))
        self.cal.shift_backward(D("2023-03-10"))

        self.assertEqual(self.cal.entries, before)

    def test_step_5_saving_stamps_a_new_revision(self):
        before = self.doc.revision
        change = self.doc.record("Moved 2023-03-09 and later one day forward")
        self.assertEqual(self.doc.revision, before + 1)
        self.assertTrue(change.at)
        self.assertTrue(change.version)


if __name__ == "__main__":
    unittest.main()
