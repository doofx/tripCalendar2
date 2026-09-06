"""Render the calendar to a JPG.

The image is drawn from the model rather than screen-grabbed, so the export does
not depend on the window being open, on how far it is scrolled, or on the screen
resolution — and it can be produced headlessly from the command line.

Pillow is the only third-party dependency in the project and it is needed only
here; :func:`available` lets the UI degrade politely when it is missing.
"""

from __future__ import annotations

import calendar as _calendar
import os
from datetime import date
from typing import Iterable, Sequence

from . import theme as theme_module
from .config import Document
from .model import WEEKDAY_HEADERS
from .version import __version__

try:  # pragma: no cover - exercised by whether Pillow is installed
    from PIL import Image, ImageDraw, ImageFont

    _PIL_ERROR: str | None = None
except ImportError as exc:  # pragma: no cover
    Image = ImageDraw = ImageFont = None  # type: ignore[assignment]
    _PIL_ERROR = str(exc)

INSTALL_HINT = "Image export needs Pillow. Install it with:  pip install Pillow"

# Layout in points; everything is multiplied by the render scale.
MARGIN = 28
TITLE_H = 62
WEEKDAY_H = 30
CELL_W = 190
CELL_MIN_H = 116
HEAD_H = 26
GAP = 8
PAD = 9
LINE_H = 15
BODY_SIZE = 11
FOOTER_H = 34

_FONT_CANDIDATES = {
    "regular": (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
        "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ),
    "bold": (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "C:/Windows/Fonts/segoeuib.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    ),
}


class ExportError(Exception):
    """Raised when the image cannot be produced."""


def available() -> bool:
    return Image is not None


def _font(kind: str, size: int):
    for path in _FONT_CANDIDATES[kind]:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def _measure(draw, text: str, font) -> float:
    return draw.textlength(text, font=font)


def _fit_prefix(draw, text: str, font, width: float) -> int:
    """Longest prefix of ``text`` that fits in ``width``, at least one character."""
    low, high = 1, len(text)
    while low < high:
        mid = (low + high + 1) // 2
        if _measure(draw, text[:mid], font) <= width:
            low = mid
        else:
            high = mid - 1
    return max(1, low)


def _wrap(draw, text: str, font, width: float) -> list[str]:
    """Wrap on spaces, hard-breaking over-long words and honouring newlines."""
    lines: list[str] = []
    for paragraph in text.split("\n"):
        if not paragraph.strip():
            lines.append("")
            continue
        current = ""
        for word in paragraph.split():
            candidate = f"{current} {word}".strip()
            if current and _measure(draw, candidate, font) > width:
                lines.append(current)
                current = word
            else:
                current = candidate
            while _measure(draw, current, font) > width and len(current) > 1:
                cut = _fit_prefix(draw, current, font, width)
                lines.append(current[:cut])
                current = current[cut:]
        if current:
            lines.append(current)
    return lines


def _rounded(draw, box, radius: int, fill=None, outline=None, width: int = 1) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def render(
    doc: Document,
    path: str,
    scale: float = 2.0,
    quality: int = 92,
    selected: date | None = None,
) -> str:
    """Draw the calendar to ``path`` as a JPG and return the path written."""
    if not available():  # pragma: no cover - depends on the environment
        raise ExportError(f"{INSTALL_HINT}\n({_PIL_ERROR})")

    settings = doc.settings
    cal = doc.calendar
    palette = theme_module.get(settings.theme)
    weeks = cal.weeks()

    s = max(1.0, float(scale))
    cell_w = int(max(CELL_W, settings.cell_width) * s)
    margin, gap, pad = int(MARGIN * s), int(GAP * s), int(PAD * s)
    head_h, line_h = int(HEAD_H * s), int(LINE_H * s)
    title_h, weekday_h = int(TITLE_H * s), int(WEEKDAY_H * s)
    footer_h = int(FOOTER_H * s)
    cell_min_h = int(max(CELL_MIN_H, settings.cell_height - 16) * s)
    radius = int(7 * s)

    f_title = _font("bold", int(22 * s))
    f_subtitle = _font("regular", int(11 * s))
    f_weekday = _font("bold", int(11 * s))
    f_daynum = _font("bold", int(15 * s))
    f_daymon = _font("regular", int(10 * s))
    f_body = _font("regular", int(BODY_SIZE * s))
    f_footer = _font("regular", int(9 * s))

    grid_w = cell_w * 7 + gap * 6
    width = grid_w + margin * 2

    # A throwaway canvas, used only to measure text before the real one is sized.
    probe = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    text_w = cell_w - pad * 2
    wrapped: dict[date, list[str]] = {}
    row_heights: list[int] = []
    for week in weeks:
        tallest = 0
        for day in week:
            text = cal.get(day)
            lines = _wrap(probe, text, f_body, text_w) if text.strip() else []
            wrapped[day] = lines
            tallest = max(tallest, len(lines))
        row_heights.append(max(cell_min_h, head_h + pad * 2 + tallest * line_h))

    height = (
        margin * 2
        + title_h
        + weekday_h
        + sum(row_heights)
        + gap * max(0, len(weeks) - 1)
        + footer_h
    )

    image = Image.new("RGB", (width, height), palette.page)
    draw = ImageDraw.Draw(image)

    # ---- title band
    band = (margin, margin, margin + grid_w, margin + title_h - int(10 * s))
    _rounded(draw, band, radius, fill=palette.header)
    draw.text(
        (margin + pad * 2, band[1] + int(10 * s)),
        settings.title,
        font=f_title,
        fill=palette.header_text,
    )
    span = (
        f"{cal.start.strftime(settings.date_format)} – "
        f"{cal.end.strftime(settings.date_format)}   ·   "
        f"{cal.week_count} weeks · {cal.day_count} days"
    )
    span_w = _measure(draw, span, f_subtitle)
    draw.text(
        (band[2] - pad * 2 - span_w, band[1] + int(20 * s)),
        span,
        font=f_subtitle,
        fill=palette.header_text,
    )

    # ---- weekday header
    top = margin + title_h
    for col, label in enumerate(WEEKDAY_HEADERS[cal.first_day]):
        x = margin + col * (cell_w + gap)
        weekend = label in ("Sat", "Sun")
        _rounded(
            draw,
            (x, top, x + cell_w, top + weekday_h - int(6 * s)),
            int(5 * s),
            fill=palette.cell_head_alt if weekend else palette.cell_head,
        )
        text = label.upper()
        draw.text(
            (x + (cell_w - _measure(draw, text, f_weekday)) / 2, top + int(5 * s)),
            text,
            font=f_weekday,
            fill=palette.accent if weekend else palette.muted,
        )

    # ---- week rows
    today = date.today()
    y = top + weekday_h
    for week, row_h in zip(weeks, row_heights):
        for col, day in enumerate(week):
            x = margin + col * (cell_w + gap)
            box = (x, y, x + cell_w, y + row_h)
            weekend = col in _weekend_columns(cal.first_day)
            is_selected = day == selected

            body = palette.surface_alt if weekend else palette.surface
            if day == today:
                body = palette.today
            _rounded(
                draw,
                box,
                radius,
                fill=body,
                outline=palette.accent if is_selected else palette.border,
                width=int((2 if is_selected else 1) * s),
            )

            # date strip
            strip = (box[0], box[1], box[2], box[1] + head_h)
            draw.rectangle(
                (strip[0] + int(1 * s), strip[1] + int(1 * s), strip[2] - int(1 * s), strip[3]),
                fill=palette.accent if is_selected else (
                    palette.cell_head_alt if weekend else palette.cell_head
                ),
            )
            draw.rectangle(
                (box[0] + int(1 * s), box[1] + int(1 * s), box[0] + int(4 * s), strip[3]),
                fill=theme_module.month_colour(palette, day.month),
            )

            head_fg = palette.accent_text if is_selected else palette.text
            draw.text(
                (box[0] + pad, box[1] + int(5 * s)),
                f"{day.day:02d}",
                font=f_daynum,
                fill=head_fg,
            )
            label = f"{_calendar.month_abbr[day.month]} {day.year}"
            draw.text(
                (box[2] - pad - _measure(draw, label, f_daymon), box[1] + int(9 * s)),
                label,
                font=f_daymon,
                fill=palette.accent_text if is_selected else palette.muted,
            )

            ty = box[1] + head_h + pad
            for line in wrapped.get(day, []):
                draw.text((box[0] + pad, ty), line, font=f_body, fill=palette.text)
                ty += line_h
        y += row_h + gap

    # ---- footer stamp
    change = doc.last_change
    stamp = f"Trip Calendar v{__version__} · revision {doc.revision}"
    if doc.saved_at:
        stamp += f" · saved {doc.saved_at}"
    if change and change.summary:
        stamp += f" · last change: {change.summary}"
    draw.text(
        (margin, height - margin - int(6 * s)),
        stamp,
        font=f_footer,
        fill=palette.muted,
    )

    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    image.save(path, "JPEG", quality=quality, subsampling=0, optimize=True)
    return path


def _weekend_columns(first_day: str) -> Sequence[int]:
    headers: Iterable[str] = WEEKDAY_HEADERS[first_day]
    return [i for i, name in enumerate(headers) if name in ("Sat", "Sun")]
