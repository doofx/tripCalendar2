"""Colour palettes shared by the on-screen grid and the exported image.

Both renderers read the same :class:`Palette`, so a saved JPG looks like what is
on screen rather than an approximation of it.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Palette:
    name: str
    page: str          # window background
    header: str        # title bar
    header_text: str
    surface: str       # day cell body
    surface_alt: str   # weekend day cell body
    cell_head: str     # date strip at the top of a cell
    cell_head_alt: str
    border: str
    text: str
    muted: str
    accent: str        # primary accent, used for the selected day
    accent_text: str
    today: str         # tint for today's cell
    toolbar: str
    #: Stripe colour per month index (1-12), so a long trip reads at a glance.
    months: tuple[str, ...]


AURORA = Palette(
    name="aurora",
    page="#eef1f6",
    header="#12304a",
    header_text="#f4f8fc",
    surface="#ffffff",
    surface_alt="#f5f8fb",
    cell_head="#e8edf4",
    cell_head_alt="#dfe7f1",
    border="#c8d3e0",
    text="#1c2733",
    muted="#71808f",
    accent="#0f8a8d",
    accent_text="#ffffff",
    today="#fff6de",
    toolbar="#e3e8ef",
    months=(
        "#5b7cfa", "#7a5bfa", "#b45bd6", "#d65b9b", "#e0645b", "#e08c3f",
        "#c9a227", "#7fae3a", "#3fae72", "#2ba3a6", "#2f8ec9", "#4a6fd4",
    ),
)

MIDNIGHT = Palette(
    name="midnight",
    page="#131820",
    header="#0b0f16",
    header_text="#e8eef7",
    surface="#1c2430",
    surface_alt="#18202b",
    cell_head="#25303f",
    cell_head_alt="#202a37",
    border="#2f3c4d",
    text="#e4ebf4",
    muted="#8b9bad",
    accent="#2fd0c5",
    accent_text="#06231f",
    today="#3a3418",
    toolbar="#1a222d",
    months=(
        "#6d8bff", "#9a7bff", "#c97ae6", "#e97ab0", "#f0837a", "#f0a65f",
        "#dcc04a", "#9ac95b", "#5cc98d", "#46bfc2", "#4aa8dd", "#6688ea",
    ),
)

PALETTES = {p.name: p for p in (AURORA, MIDNIGHT)}
DEFAULT_THEME = AURORA.name


def get(name: str | None) -> Palette:
    return PALETTES.get((name or "").lower(), PALETTES[DEFAULT_THEME])


def month_colour(palette: Palette, month: int) -> str:
    return palette.months[(month - 1) % 12]
