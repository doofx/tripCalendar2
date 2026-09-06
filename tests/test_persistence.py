"""Tests for the fixes to saving, reopening and knowing what is unsaved.

These cover the three faults reported from a real run: a save that landed
somewhere the user could not find, a plan that still claimed to be unsaved
straight after saving, and a window that would not close.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tripcalendar import config, paths, session  # noqa: E402


class ConfigFolder(unittest.TestCase):
    def test_the_config_folder_sits_next_to_the_application(self):
        # Not the working directory: the app is normally started from elsewhere.
        self.assertEqual(paths.config_dir(), os.path.join(paths.app_dir(), "config"))
        self.assertTrue(os.path.isabs(paths.config_dir()))

    def test_no_argument_means_the_default_plan_in_the_config_folder(self):
        self.assertEqual(paths.resolve(None), paths.default_plan_path())
        self.assertEqual(
            os.path.dirname(paths.default_plan_path()), paths.config_dir()
        )

    def test_a_bare_filename_is_looked_up_in_the_config_folder(self):
        self.assertEqual(
            paths.resolve("japan.xml"), os.path.join(paths.config_dir(), "japan.xml")
        )

    def test_an_explicit_path_is_honoured_as_given(self):
        given = os.path.join("subdir", "japan.xml")
        self.assertEqual(paths.resolve(given), os.path.abspath(given))

    def test_an_absolute_path_is_honoured_as_given(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "japan.xml")
            self.assertEqual(paths.resolve(target), os.path.normpath(target))

    def test_the_shipped_example_lives_in_the_config_folder(self):
        self.assertTrue(
            os.path.exists(os.path.join(paths.config_dir(), "example_trip.xml"))
        )


class AlwaysAConfigFile(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "trip_calendar.xml")

    def test_first_run_creates_the_file(self):
        self.assertFalse(os.path.exists(self.path))
        doc = config.ensure_plan(self.path)
        self.assertTrue(os.path.exists(self.path))
        self.assertEqual(doc.path, self.path)

    def test_a_second_run_reuses_it_rather_than_replacing_it(self):
        first = config.ensure_plan(self.path)
        first.calendar.set(first.calendar.start, "Pack")
        config.save(first)

        second = config.ensure_plan(self.path)
        self.assertEqual(second.calendar.get(second.calendar.start), "Pack")

    def test_saving_returns_an_absolute_path_so_it_can_be_reported(self):
        doc = config.ensure_plan(self.path)
        written = config.save(doc)
        self.assertTrue(os.path.isabs(written))
        self.assertTrue(os.path.exists(written))


class UnsavedWork(unittest.TestCase):
    """The plan is dirty only when it actually differs from the file."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.doc = config.ensure_plan(os.path.join(self.tmp.name, "trip.xml"))
        self.saved = config.fingerprint(self.doc)

    def test_saving_leaves_nothing_outstanding(self):
        self.doc.calendar.set(self.doc.calendar.start, "Fly out")
        self.assertNotEqual(config.fingerprint(self.doc), self.saved)

        config.save(self.doc)
        self.assertEqual(config.fingerprint(self.doc), config.fingerprint(self.doc))
        saved_now = config.fingerprint(self.doc)

        # Nothing has been touched since, so closing must not prompt.
        self.assertEqual(config.fingerprint(self.doc), saved_now)

    def test_a_saved_plan_reloads_to_the_same_fingerprint(self):
        self.doc.calendar.set(self.doc.calendar.start, "Fly out")
        self.doc.settings.title = "Japan"
        config.save(self.doc)

        reloaded = config.load(self.doc.path)
        self.assertEqual(config.fingerprint(reloaded), config.fingerprint(self.doc))

    def test_editing_a_day_counts_as_a_change(self):
        self.doc.calendar.set(self.doc.calendar.start, "Fly out")
        self.assertNotEqual(config.fingerprint(self.doc), self.saved)

    def test_shifting_days_counts_as_a_change(self):
        self.doc.calendar.set(self.doc.calendar.start, "Fly out")
        config.save(self.doc)
        saved = config.fingerprint(self.doc)
        self.doc.calendar.shift_forward(self.doc.calendar.start)
        self.assertNotEqual(config.fingerprint(self.doc), saved)

    def test_recording_history_alone_does_not_count_as_a_change(self):
        # History and timestamps are bookkeeping, not unsaved trip content.
        self.doc.record("something happened")
        self.assertEqual(config.fingerprint(self.doc), self.saved)


class LastOpenedFile(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state_path = os.path.join(self.tmp.name, "app_state.xml")

    def test_state_round_trips(self):
        state = session.AppState()
        state.remember(os.path.join(self.tmp.name, "japan.xml"))
        state.window = "1360x880+120+60"
        session.save(state, self.state_path)

        reloaded = session.load(self.state_path)
        self.assertEqual(reloaded.last_file, state.last_file)
        self.assertEqual(reloaded.window, "1360x880+120+60")

    def test_remembering_stores_an_absolute_path(self):
        state = session.AppState()
        state.remember("japan.xml")
        self.assertTrue(os.path.isabs(state.last_file))

    def test_a_missing_state_file_is_not_an_error(self):
        state = session.load(os.path.join(self.tmp.name, "absent.xml"))
        self.assertEqual(state.last_file, "")

    def test_a_corrupt_state_file_does_not_stop_startup(self):
        with open(self.state_path, "w", encoding="utf-8") as handle:
            handle.write("<appState><lastFile>")
        self.assertEqual(session.load(self.state_path).last_file, "")

    def test_startup_reopens_the_last_plan(self):
        plan = os.path.join(self.tmp.name, "japan.xml")
        config.ensure_plan(plan)
        state = session.AppState(last_file=plan)
        self.assertEqual(session.startup_plan_path(None, state), plan)

    def test_an_explicit_argument_wins_over_the_remembered_file(self):
        remembered = os.path.join(self.tmp.name, "japan.xml")
        config.ensure_plan(remembered)
        asked_for = os.path.join(self.tmp.name, "peru.xml")
        state = session.AppState(last_file=remembered)
        self.assertEqual(session.startup_plan_path(asked_for, state), asked_for)

    def test_a_remembered_file_that_has_vanished_falls_back_to_the_default(self):
        state = session.AppState(last_file=os.path.join(self.tmp.name, "deleted.xml"))
        self.assertEqual(
            session.startup_plan_path(None, state), paths.default_plan_path()
        )


if __name__ == "__main__":
    unittest.main()
