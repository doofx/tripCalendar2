"""Tests for the parts of the image exporter that do not need Pillow.

Text layout is where the renderer can actually get things wrong, so it is
measured through a stub that charges a fixed width per character. The drawing
itself needs Pillow and is skipped when it is not installed.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tripcalendar import config, imaging  # noqa: E402
from tripcalendar.model import MONDAY, SUNDAY  # noqa: E402

CHAR_W = 7.0


class StubDraw:
    """Stands in for an ImageDraw: every character is CHAR_W wide."""

    def textlength(self, text: str, font=None) -> float:
        return len(text) * CHAR_W


def wrap(text: str, chars: int) -> list[str]:
    return imaging._wrap(StubDraw(), text, None, chars * CHAR_W)


class Wrapping(unittest.TestCase):
    def test_short_text_stays_on_one_line(self):
        self.assertEqual(wrap("Sleep: Tokyo", 20), ["Sleep: Tokyo"])

    def test_explicit_newlines_are_kept(self):
        self.assertEqual(wrap("Osaka\nSleep: Osaka", 20), ["Osaka", "Sleep: Osaka"])

    def test_blank_lines_are_kept(self):
        self.assertEqual(wrap("a\n\nb", 20), ["a", "", "b"])

    def test_long_text_wraps_on_spaces(self):
        lines = wrap("Stop at Toyota Kaikan Museum near Nagoya", 12)
        self.assertTrue(all(len(line) <= 12 for line in lines))
        self.assertEqual(" ".join(lines), "Stop at Toyota Kaikan Museum near Nagoya")

    def test_a_word_wider_than_the_cell_is_hard_broken(self):
        lines = wrap("Llanfairpwllgwyngyll", 8)
        self.assertTrue(all(len(line) <= 8 for line in lines))
        self.assertEqual("".join(lines), "Llanfairpwllgwyngyll")

    def test_wrapping_never_loses_characters(self):
        # Wrapping may consume the space it breaks at, and may split a word that
        # is too wide to fit, but no other character may be lost or reordered.
        text = "Kyoto - day trip to Nara + Fushimi Inari temple\nSleep: Kyoto"
        expected = "".join(text.split())
        for chars in range(4, 40):
            lines = wrap(text, chars)
            self.assertEqual("".join("".join(l.split()) for l in lines), expected,
                             f"width {chars}")
            self.assertTrue(all(len(line) <= chars for line in lines), f"width {chars}")

    def test_wrapping_terminates_on_a_one_character_cell(self):
        self.assertEqual(wrap("abc", 1), ["a", "b", "c"])


class Columns(unittest.TestCase):
    def test_weekend_columns_follow_the_week_start(self):
        self.assertEqual(list(imaging._weekend_columns(SUNDAY)), [0, 6])
        self.assertEqual(list(imaging._weekend_columns(MONDAY)), [5, 6])


class _StubImage:
    """Records the drawing calls render() makes, in place of a real Pillow image."""

    def __init__(self, mode, size, colour=None):
        self.mode, self.width, self.height = mode, size[0], size[1]
        self.saved = None

    def save(self, path, fmt=None, **options):
        self.saved = (path, fmt, options)
        with open(path, "wb") as handle:
            handle.write(b"stub")


class _StubDrawer:
    def __init__(self, image=None):
        self.image = image
        self.texts = []

    def textlength(self, text, font=None):
        return len(text) * CHAR_W

    def text(self, xy, text, font=None, fill=None):
        self.texts.append((xy, text))

    def rectangle(self, box, fill=None, outline=None, width=1):
        pass

    def rounded_rectangle(self, box, radius=0, fill=None, outline=None, width=1):
        pass


class _StubImageModule:
    last = None

    @classmethod
    def new(cls, mode, size, colour=None):
        cls.last = _StubImage(mode, size, colour)
        return cls.last


class _StubDrawModule:
    @staticmethod
    def Draw(image):
        return _StubDrawer(image)


class _StubFontModule:
    @staticmethod
    def truetype(path, size):
        return ("truetype", size)

    @staticmethod
    def load_default():
        return ("default", 10)


class Layout(unittest.TestCase):
    """Drive the whole render path with stubs, checking the geometry it computes."""

    def setUp(self):
        self.patched = {
            "Image": _StubImageModule,
            "ImageDraw": _StubDrawModule,
            "ImageFont": _StubFontModule,
        }
        self.originals = {name: getattr(imaging, name) for name in self.patched}
        for name, stub in self.patched.items():
            setattr(imaging, name, stub)
        self.addCleanup(self._restore)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def _restore(self):
        for name, original in self.originals.items():
            setattr(imaging, name, original)

    def render(self, doc, scale=1.0):
        path = os.path.join(self.tmp.name, "out.jpg")
        imaging.render(doc, path, scale=scale)
        return _StubImageModule.last

    def plan(self, weeks=2, **days):
        doc = config.new_document(os.path.join(self.tmp.name, "plan.xml"))
        doc.calendar.end = doc.calendar.start + timedelta(days=weeks * 7 - 1)
        doc.calendar.normalise()
        for offset, text in days.items():
            day = doc.calendar.start + timedelta(days=int(offset.lstrip("d")))
            doc.calendar.set(day, text)
        return doc

    def test_it_saves_a_jpeg(self):
        image = self.render(self.plan())
        path, fmt, options = image.saved
        self.assertTrue(path.endswith(".jpg"))
        self.assertEqual(fmt, "JPEG")
        self.assertEqual(options["quality"], 92)
        self.assertEqual(image.mode, "RGB")

    def test_the_image_is_seven_columns_wide(self):
        image = self.render(self.plan())
        expected = imaging.CELL_W * 7 + imaging.GAP * 6 + imaging.MARGIN * 2
        self.assertEqual(image.width, expected)

    def test_more_weeks_make_a_taller_image(self):
        short = self.render(self.plan(weeks=2)).height
        tall = self.render(self.plan(weeks=5)).height
        self.assertGreater(tall, short)
        self.assertAlmostEqual(
            tall - short, 3 * (imaging.CELL_MIN_H + imaging.GAP), delta=2
        )

    def test_a_wordy_day_makes_its_row_taller(self):
        plain = self.render(self.plan(weeks=1)).height
        wordy = self.render(self.plan(weeks=1, d2="word " * 200)).height
        self.assertGreater(wordy, plain)

    def test_every_day_with_text_is_drawn(self):
        doc = self.plan(weeks=2, d1="Osaka", d9="Kyoto")
        drawn = []
        original = _StubDrawModule.Draw

        def capture(image):
            drawer = original(image)
            drawn.append(drawer)
            return drawer

        _StubDrawModule.Draw = staticmethod(capture)
        self.addCleanup(lambda: setattr(_StubDrawModule, "Draw", staticmethod(original)))
        self.render(doc)
        painted = {text for drawer in drawn for _xy, text in drawer.texts}
        self.assertIn("Osaka", painted)
        self.assertIn("Kyoto", painted)

    def test_the_footer_carries_the_version_and_revision(self):
        doc = self.plan()
        doc.record("Moved a day forward")
        config.save(doc)
        drawn = []
        original = _StubDrawModule.Draw

        def capture(image):
            drawer = original(image)
            drawn.append(drawer)
            return drawer

        _StubDrawModule.Draw = staticmethod(capture)
        self.addCleanup(lambda: setattr(_StubDrawModule, "Draw", staticmethod(original)))
        self.render(doc)
        painted = " ".join(text for drawer in drawn for _xy, text in drawer.texts)
        self.assertIn(f"v{imaging.__version__}", painted)
        self.assertIn("revision 1", painted)
        self.assertIn("Moved a day forward", painted)

    def test_scale_multiplies_the_geometry(self):
        single = self.render(self.plan(), scale=1.0)
        double = self.render(self.plan(), scale=2.0)
        self.assertAlmostEqual(double.width / single.width, 2.0, delta=0.02)


class Rendering(unittest.TestCase):
    @unittest.skipUnless(imaging.available(), "Pillow is not installed")
    def test_it_writes_a_jpeg(self):
        from PIL import Image

        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        doc = config.load(os.path.join(here, "example_trip.xml"))
        with tempfile.TemporaryDirectory() as tmp:
            path = imaging.render(doc, os.path.join(tmp, "out.jpg"), scale=1.0)
            self.assertTrue(os.path.exists(path))
            with Image.open(path) as image:
                self.assertEqual(image.format, "JPEG")
                self.assertGreater(image.width, 800)
                self.assertGreater(image.height, 400)

    @unittest.skipIf(imaging.available(), "Pillow is installed")
    def test_it_explains_itself_when_pillow_is_missing(self):
        doc = config.new_document()
        with self.assertRaises(imaging.ExportError) as caught:
            imaging.render(doc, "unused.jpg")
        self.assertIn("pip install Pillow", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
