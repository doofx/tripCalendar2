"""Tkinter front end: a week-per-row grid of editable day boxes.

Layout mirrors a wall planner. Each row is one week running left to right from
the configured first day (Sunday by default), each day is a card with a date
strip and a free-text box, and the whole grid scrolls vertically.

The two shift buttons are the reason the grid exists: pick a day, and the
selected day together with everything after it slides one day later or one day
earlier, so a plan can absorb a delay without being retyped.
"""

from __future__ import annotations

import calendar as _calendar
import os
import sys
import tkinter as tk
import traceback
from datetime import date, timedelta
from tkinter import filedialog, font as tkfont, messagebox, ttk

from . import config as config_module
from . import imaging
from . import paths
from . import session as session_module
from . import theme as theme_module
from .model import MONDAY, SUNDAY, ShiftConflict, TripCalendar, WEEKDAY_HEADERS
from .version import BUILD_TIMESTAMP, __version__, version_banner

WEEKEND_NAMES = ("Sat", "Sun")


class DayCell:
    """One day of the grid: a date strip plus the text box under it."""

    def __init__(self, parent: tk.Widget, app: "TripCalendarApp", day: date) -> None:
        self.app = app
        self.day = day
        palette = app.palette
        weekend = day.strftime("%a") in WEEKEND_NAMES

        self.frame = tk.Frame(
            parent,
            background=palette.surface_alt if weekend else palette.surface,
            highlightthickness=1,
            highlightbackground=palette.border,
            highlightcolor=palette.border,
            bd=0,
        )

        self.head = tk.Frame(
            self.frame,
            background=palette.cell_head_alt if weekend else palette.cell_head,
            height=24,
        )
        self.head.pack(fill="x", side="top")

        self.stripe = tk.Frame(
            self.head, background=theme_module.month_colour(palette, day.month), width=4
        )
        self.stripe.pack(side="left", fill="y")

        self.number = tk.Label(
            self.head,
            text=f"{day.day:02d}",
            font=app.f_daynum,
            background=self.head["background"],
            foreground=palette.text,
            padx=6,
        )
        self.number.pack(side="left")

        self.month = tk.Label(
            self.head,
            text=f"{_calendar.month_abbr[day.month]} {day.year}",
            font=app.f_daymon,
            background=self.head["background"],
            foreground=palette.muted,
            padx=6,
        )
        self.month.pack(side="right")

        self.text = tk.Text(
            self.frame,
            wrap="word",
            font=app.f_body,
            background=self.frame["background"],
            foreground=palette.text,
            insertbackground=palette.accent,
            relief="flat",
            highlightthickness=0,
            borderwidth=0,
            padx=7,
            pady=6,
            height=app.body_lines,  # fixed: every day is the same size, always
            width=1,  # the grid column sets the real width
            undo=True,
            maxundo=200,
        )
        # The scrollbar appears only when a day has more text than fits, so the
        # grid stays quiet, and it is packed before the text so pack gives it
        # room instead of letting the text claim the whole cell.
        self.scroll = ttk.Scrollbar(
            self.frame,
            orient="vertical",
            style="Cell.Vertical.TScrollbar",
            command=self.text.yview,
        )
        self._scroll_shown = False
        self.text.configure(yscrollcommand=self._on_text_scrolled)
        self.text.pack(side="left", fill="both", expand=True)

        self.text.bind("<FocusIn>", self._on_focus)
        self.text.bind("<<Modified>>", self._on_modified)
        for widget in (self.frame, self.head, self.number, self.month, self.stripe):
            widget.bind("<Button-1>", self._on_click)
        # Only the text box itself can swallow the wheel; over the date strip
        # or the cell border it always scrolls the page.
        for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.text.bind(sequence, self._on_wheel)
        app.bind_scroll(self.frame)
        app.bind_scroll(self.head)
        app.bind_scroll(self.number)
        app.bind_scroll(self.month)

    # ------------------------------------------------------------- content

    def load(self, value: str) -> None:
        self.text.delete("1.0", "end")
        if value:
            self.text.insert("1.0", value)
        self.text.edit_modified(False)

    def value(self) -> str:
        return self.text.get("1.0", "end-1c")

    def overflowing(self) -> bool:
        """True when the day holds more text than the fixed box can show."""
        first, last = self.text.yview()
        return not (first <= 0.0 and last >= 1.0)

    def _on_text_scrolled(self, first: str, last: str) -> None:
        """Track the view and show the scrollbar only while it is needed."""
        self.scroll.set(first, last)
        needed = not (float(first) <= 0.0 and float(last) >= 1.0)
        if needed and not self._scroll_shown:
            try:
                self.scroll.pack(side="right", fill="y", before=self.text)
            except tk.TclError:  # pragma: no cover - text not packed yet
                self.scroll.pack(side="right", fill="y")
            self._scroll_shown = True
        elif not needed and self._scroll_shown:
            self.scroll.pack_forget()
            self._scroll_shown = False

    def _on_wheel(self, event: tk.Event) -> str:
        """Scroll this day if it has hidden text, otherwise scroll the page.

        Reaching either end of a day hands the wheel back to the page, so one
        continuous scroll never gets stuck inside a single box.
        """
        down = getattr(event, "num", None) == 5 or getattr(event, "delta", 0) < 0
        step = 1 if down else -1
        if self.overflowing():
            first, last = self.text.yview()
            at_edge = (step < 0 and first <= 0.0) or (step > 0 and last >= 1.0)
            if not at_edge:
                self.text.yview_scroll(step, "units")
                return "break"
        return self.app.scroll_page(step)

    # ------------------------------------------------------------- events

    def _on_click(self, _event: tk.Event) -> str:
        self.text.focus_set()
        return "break"

    def _on_focus(self, _event: tk.Event) -> None:
        self.app.select(self.day)

    def _on_modified(self, _event: tk.Event) -> None:
        if not self.text.edit_modified():
            return
        self.text.edit_modified(False)
        self.app.on_cell_edited(self)

    # ------------------------------------------------------------- styling

    def restyle(self, selected: bool, today: bool) -> None:
        palette = self.app.palette
        weekend = self.day.strftime("%a") in WEEKEND_NAMES
        body = palette.surface_alt if weekend else palette.surface
        if today:
            body = palette.today
        head = palette.cell_head_alt if weekend else palette.cell_head
        if selected:
            head = palette.accent

        self.frame.configure(
            background=body,
            highlightthickness=2 if selected else 1,
            highlightbackground=palette.accent if selected else palette.border,
            highlightcolor=palette.accent if selected else palette.border,
        )
        self.text.configure(background=body, foreground=palette.text)
        self.head.configure(background=head)
        fg = palette.accent_text if selected else palette.text
        self.number.configure(background=head, foreground=fg)
        self.month.configure(
            background=head,
            foreground=palette.accent_text if selected else palette.muted,
        )


class TripCalendarApp(tk.Tk):
    """The main window."""

    def __init__(
        self,
        doc: config_module.Document,
        state: session_module.AppState | None = None,
    ) -> None:
        super().__init__()
        self.doc = doc
        self.state = state if state is not None else session_module.AppState()
        self.palette = theme_module.get(doc.settings.theme)
        self.selected: date | None = None
        self.cells: dict[date, DayCell] = {}
        self.rows: list[list[date]] = []
        self._building = False
        # Whether there is unsaved work is decided by comparing the plan against
        # what was last written, not by a flag that events can leave stuck on.
        self._saved_fingerprint = config_module.fingerprint(doc)

        self.title(f"{doc.settings.title} — Trip Calendar {version_banner()}")
        self.minsize(900, 560)
        self.geometry("1360x880")
        # Older files kept the window position inside the plan itself; honour it
        # so upgrading does not throw away where someone had put the window.
        remembered = self.state.window or doc.settings.extra.get("window", "")
        if remembered:
            try:
                self.geometry(remembered)
            except tk.TclError:
                pass  # a stale geometry string must not stop the app opening

        self._build_fonts()
        self._build_styles()
        self._build_menu()
        self._build_chrome()
        self.rebuild()

        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self._bind_shortcuts()
        self.report_load_warnings()

    def report_callback_exception(self, exc, value, tb) -> None:
        """Show what went wrong rather than printing to a console nobody sees."""
        details = "".join(traceback.format_exception(exc, value, tb))
        print(details, file=sys.stderr)
        try:
            messagebox.showerror(
                "Something went wrong",
                f"{value}\n\nThe window is still open; your plan has not been "
                f"changed by this error.\n\n{details[-1500:]}",
                parent=self,
            )
        except tk.TclError:  # pragma: no cover - the dialog itself failed
            pass

    # ------------------------------------------------------------ calendar

    @property
    def calendar(self) -> TripCalendar:
        return self.doc.calendar

    # -------------------------------------------------------------- chrome

    def _build_fonts(self) -> None:
        scale = max(0.6, min(2.5, self.doc.settings.font_scale))

        def size(points: int) -> int:
            return max(7, int(round(points * scale)))

        family = self._pick_family()
        self.f_title = tkfont.Font(family=family, size=size(17), weight="bold")
        self.f_subtitle = tkfont.Font(family=family, size=size(9))
        self.f_weekday = tkfont.Font(family=family, size=size(9), weight="bold")
        self.f_daynum = tkfont.Font(family=family, size=size(12), weight="bold")
        self.f_daymon = tkfont.Font(family=family, size=size(8))
        self.f_body = tkfont.Font(family=family, size=size(9))
        self.f_status = tkfont.Font(family=family, size=size(8))
        self.body_lines = max(4, int(self.doc.settings.cell_height / 22))

    def _pick_family(self) -> str:
        available = set(tkfont.families(self))
        for candidate in ("Segoe UI", "Inter", "Helvetica Neue", "DejaVu Sans", "Helvetica"):
            if candidate in available:
                return candidate
        return "TkDefaultFont"

    def _build_styles(self) -> None:
        palette = self.palette
        self.configure(background=palette.page)
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:  # pragma: no cover - platform dependent
            pass
        style.configure("TFrame", background=palette.page)
        style.configure(
            "Toolbar.TFrame", background=palette.toolbar, relief="flat", borderwidth=0
        )
        style.configure(
            "Tool.TButton",
            background=palette.toolbar,
            foreground=palette.text,
            borderwidth=0,
            focusthickness=0,
            padding=(12, 7),
            font=self.f_subtitle,
        )
        style.map(
            "Tool.TButton",
            background=[("active", palette.cell_head), ("pressed", palette.border)],
        )
        style.configure(
            "Accent.TButton",
            background=palette.accent,
            foreground=palette.accent_text,
            borderwidth=0,
            focusthickness=0,
            padding=(14, 7),
            font=self.f_subtitle,
        )
        style.map(
            "Accent.TButton",
            background=[("active", palette.header), ("pressed", palette.header)],
            foreground=[("active", palette.header_text)],
        )
        style.configure(
            "Vertical.TScrollbar",
            background=palette.border,
            troughcolor=palette.page,
            borderwidth=0,
            arrowcolor=palette.muted,
        )
        style.configure(
            "Cell.Vertical.TScrollbar",
            background=palette.border,
            troughcolor=palette.surface_alt,
            borderwidth=0,
            arrowsize=9,
            width=9,
            arrowcolor=palette.muted,
        )

    def _build_menu(self) -> None:
        menubar = tk.Menu(self)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="New…", command=self.action_new)
        file_menu.add_command(label="Open…", accelerator="Ctrl+O", command=self.action_open)
        file_menu.add_separator()
        file_menu.add_command(label="Save", accelerator="Ctrl+S", command=self.action_save)
        file_menu.add_command(label="Save As…", command=self.action_save_as)
        file_menu.add_command(
            label="Export as JPG…", accelerator="Ctrl+E", command=self.action_export
        )
        file_menu.add_separator()
        file_menu.add_command(label="Quit", command=self.on_close)
        menubar.add_cascade(label="File", menu=file_menu)

        edit_menu = tk.Menu(menubar, tearoff=0)
        edit_menu.add_command(
            label="Move day (and later) backward",
            accelerator="Ctrl+Left",
            command=self.action_move_left,
        )
        edit_menu.add_command(
            label="Move day (and later) forward",
            accelerator="Ctrl+Right",
            command=self.action_move_right,
        )
        edit_menu.add_separator()
        edit_menu.add_command(label="Clear selected day", command=self.action_clear_day)
        edit_menu.add_command(label="Add week at start", command=self.action_week_start)
        edit_menu.add_command(label="Add week at end", command=self.action_week_end)
        edit_menu.add_command(label="Trim empty weeks", command=self.action_trim)
        menubar.add_cascade(label="Edit", menu=edit_menu)

        view_menu = tk.Menu(menubar, tearoff=0)
        for name in theme_module.PALETTES:
            view_menu.add_command(
                label=f"Theme: {name.title()}",
                command=lambda n=name: self.action_theme(n),
            )
        view_menu.add_separator()
        view_menu.add_command(label="Calendar settings…", command=self.action_settings)
        menubar.add_cascade(label="View", menu=view_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About", command=self.action_about)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.configure(menu=menubar)

    def _build_chrome(self) -> None:
        palette = self.palette

        header = tk.Frame(self, background=palette.header)
        header.pack(fill="x", side="top")
        self.title_label = tk.Label(
            header,
            text=self.doc.settings.title,
            font=self.f_title,
            background=palette.header,
            foreground=palette.header_text,
            padx=18,
            pady=12,
        )
        self.title_label.pack(side="left")
        self.range_label = tk.Label(
            header,
            text="",
            font=self.f_subtitle,
            background=palette.header,
            foreground=palette.header_text,
            padx=18,
        )
        self.range_label.pack(side="right")

        self.weekday_bar = tk.Frame(self, background=palette.page, padx=14, pady=(8))
        self.weekday_bar.pack(fill="x", side="top")

        body = tk.Frame(self, background=palette.page)
        body.pack(fill="both", expand=True, side="top")

        self.canvas = tk.Canvas(
            body, background=palette.page, highlightthickness=0, borderwidth=0
        )
        self.scroll = ttk.Scrollbar(
            body, orient="vertical", command=self.canvas.yview, style="Vertical.TScrollbar"
        )
        self.canvas.configure(yscrollcommand=self.scroll.set)
        self.scroll.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.grid_frame = tk.Frame(self.canvas, background=palette.page, padx=14, pady=6)
        self.grid_window = self.canvas.create_window(
            (0, 0), window=self.grid_frame, anchor="nw"
        )
        self.grid_frame.bind(
            "<Configure>",
            lambda _e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self.canvas.bind("<Configure>", self._on_canvas_resize)
        self.bind_scroll(self.canvas)

        self.toolbar = ttk.Frame(self, style="Toolbar.TFrame", padding=(14, 10))
        self.toolbar.pack(fill="x", side="bottom")
        self._build_toolbar()

        self.status = tk.Label(
            self,
            text="",
            font=self.f_status,
            background=palette.page,
            foreground=palette.muted,
            anchor="w",
            padx=16,
            pady=5,
        )
        self.status.pack(fill="x", side="bottom")

    def _build_toolbar(self) -> None:
        left = ttk.Frame(self.toolbar, style="Toolbar.TFrame")
        left.pack(side="left")
        right = ttk.Frame(self.toolbar, style="Toolbar.TFrame")
        right.pack(side="right")

        ttk.Button(
            left, text="◀  Move Left", style="Accent.TButton", command=self.action_move_left
        ).pack(side="left", padx=(0, 8))
        ttk.Button(
            left, text="Move Right  ▶", style="Accent.TButton", command=self.action_move_right
        ).pack(side="left", padx=(0, 18))
        ttk.Button(
            left, text="+ Week at start", style="Tool.TButton", command=self.action_week_start
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            left, text="+ Week at end", style="Tool.TButton", command=self.action_week_end
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            left, text="Trim empty weeks", style="Tool.TButton", command=self.action_trim
        ).pack(side="left")

        ttk.Button(
            right, text="Settings", style="Tool.TButton", command=self.action_settings
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            right, text="Save as image", style="Tool.TButton", command=self.action_export
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            right, text="Save", style="Accent.TButton", command=self.action_save
        ).pack(side="left")

    def _bind_shortcuts(self) -> None:
        self.bind_all("<Control-s>", lambda _e: self.action_save())
        self.bind_all("<Control-e>", lambda _e: self.action_export())
        self.bind_all("<Control-o>", lambda _e: self.action_open())
        self.bind_all("<Control-Left>", lambda _e: self.action_move_left())
        self.bind_all("<Control-Right>", lambda _e: self.action_move_right())

    # ------------------------------------------------------------ scrolling

    def bind_scroll(self, widget: tk.Widget) -> None:
        widget.bind("<MouseWheel>", self._on_wheel)
        widget.bind("<Button-4>", self._on_wheel)
        widget.bind("<Button-5>", self._on_wheel)

    def _on_wheel(self, event: tk.Event) -> str:
        down = getattr(event, "num", None) == 5 or getattr(event, "delta", 0) < 0
        return self.scroll_page(1 if down else -1)

    def scroll_page(self, step: int) -> str:
        """Scroll the week grid. Day cells hand the wheel back to this."""
        self.canvas.yview_scroll(step, "units")
        return "break"

    def _on_canvas_resize(self, event: tk.Event) -> None:
        self.canvas.itemconfigure(self.grid_window, width=event.width)

    # --------------------------------------------------------------- build

    def rebuild(self) -> None:
        """Recreate the whole grid from the model."""
        self._building = True
        try:
            for child in self.grid_frame.winfo_children():
                child.destroy()
            for child in self.weekday_bar.winfo_children():
                child.destroy()
            self.cells.clear()

            palette = self.palette
            cal = self.calendar
            self.rows = cal.weeks()

            for col, label in enumerate(WEEKDAY_HEADERS[cal.first_day]):
                weekend = label in WEEKEND_NAMES
                tk.Label(
                    self.weekday_bar,
                    text=label.upper(),
                    font=self.f_weekday,
                    background=palette.cell_head_alt if weekend else palette.cell_head,
                    foreground=palette.accent if weekend else palette.muted,
                    pady=4,
                ).grid(row=0, column=col, sticky="ew", padx=3)
                self.weekday_bar.columnconfigure(
                    col, weight=1, uniform="day", minsize=self.doc.settings.cell_width
                )
            # Keep the header aligned with the grid, which loses the scrollbar width.
            self.weekday_bar.columnconfigure(7, minsize=self.scroll.winfo_reqwidth())

            for row_index, week in enumerate(self.rows):
                for col, day in enumerate(week):
                    cell = DayCell(self.grid_frame, self, day)
                    cell.frame.grid(row=row_index, column=col, sticky="nsew", padx=3, pady=3)
                    cell.load(cal.get(day))
                    self.cells[day] = cell
                self.grid_frame.rowconfigure(row_index, weight=0)

            for col in range(7):
                self.grid_frame.columnconfigure(
                    col, weight=1, uniform="day", minsize=self.doc.settings.cell_width
                )

            if self.selected not in self.cells:
                self.selected = None
            self.restyle_cells()
            self.refresh_header()
        finally:
            self._building = False
        self.after_idle(
            lambda: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

    def restyle_cells(self) -> None:
        today = date.today()
        for day, cell in self.cells.items():
            cell.restyle(selected=day == self.selected, today=day == today)

    def refresh_header(self) -> None:
        cal = self.calendar
        fmt = self.doc.settings.date_format
        self.title_label.configure(text=self.doc.settings.title)
        self.range_label.configure(
            text=f"{cal.start.strftime(fmt)}  –  {cal.end.strftime(fmt)}      "
            f"{cal.week_count} weeks · {cal.day_count} days"
        )
        marker = "*" if self.is_dirty() else ""
        self.title(
            f"{marker}{self.doc.settings.title} — Trip Calendar {version_banner()}"
        )
        self.refresh_status()

    def refresh_status(self, message: str = "") -> None:
        parts = [f"v{__version__}", f"revision {self.doc.revision}"]
        if self.doc.saved_at:
            parts.append(f"saved {self.doc.saved_at}")
        parts.append(os.path.basename(self.doc.path))
        if self.selected:
            parts.append(f"selected {self.selected.strftime(self.doc.settings.date_format)}")
        if self.is_dirty():
            parts.append("unsaved changes")
        if message:
            parts.append(message)
        elif self.doc.last_change:
            parts.append(f"last change: {self.doc.last_change.summary}")
        self.status.configure(text="   ·   ".join(parts))

    # -------------------------------------------------------------- state

    def select(self, day: date) -> None:
        if self.selected == day:
            return
        self.selected = day
        self.restyle_cells()
        self.refresh_status()

    def on_cell_edited(self, cell: DayCell) -> None:
        if self._building:
            return
        self.calendar.set(cell.day, cell.value())
        self.mark_dirty()

    def is_dirty(self) -> bool:
        """True when the plan differs from what was last written to disk.

        Derived rather than remembered, so a save always clears it and a stray
        widget event can never leave the app convinced it has unsaved work.
        """
        return config_module.fingerprint(self.doc) != self._saved_fingerprint

    def mark_saved(self) -> None:
        self._saved_fingerprint = config_module.fingerprint(self.doc)

    def mark_dirty(self, message: str = "") -> None:
        self.refresh_header()
        if message:
            self.refresh_status(message)

    def flush(self) -> None:
        """Push every visible text box back into the model."""
        for day, cell in self.cells.items():
            self.calendar.set(day, cell.value())

    def require_selection(self) -> date | None:
        if self.selected is None:
            messagebox.showinfo(
                "Pick a day first",
                "Click a day in the grid, then use Move Left or Move Right.\n\n"
                "The selected day and every day after it move together.",
                parent=self,
            )
            return None
        return self.selected

    # ------------------------------------------------------------ actions

    def action_move_right(self) -> None:
        anchor = self.require_selection()
        if anchor is None:
            return
        self.flush()
        result = self.calendar.shift_forward(anchor)
        self._after_shift(result)

    def action_move_left(self) -> None:
        anchor = self.require_selection()
        if anchor is None:
            return
        self.flush()
        try:
            result = self.calendar.shift_backward(anchor)
        except ShiftConflict as clash:
            preview = clash.text.strip().splitlines()[0][:80]
            keep_going = messagebox.askokcancel(
                "Overwrite the previous day?",
                f"{clash.victim.strftime(self.doc.settings.date_format)} already has text:\n\n"
                f"    {preview}\n\n"
                "Moving backward will replace it. Continue?",
                icon="warning",
                parent=self,
            )
            if not keep_going:
                return
            result = self.calendar.shift_backward(anchor, force=True)
        self._after_shift(result)

    def _after_shift(self, result) -> None:
        self.doc.record(result.summary)
        self.selected = result.anchor + timedelta(days=result.direction)
        self.rebuild()
        moved = self.cells.get(self.selected)
        if moved is not None:  # keep typing where the text ended up
            moved.text.focus_set()
        self.refresh_status(result.summary)

    def action_week_start(self) -> None:
        self.flush()
        self.calendar.prepend_week()
        self.doc.record("Added a week at the start")
        self.rebuild()

    def action_week_end(self) -> None:
        self.flush()
        self.calendar.append_week()
        self.doc.record("Added a week at the end")
        self.rebuild()

    def action_trim(self) -> None:
        self.flush()
        removed = self.calendar.trim_empty_weeks()
        if not removed:
            self.refresh_status("No empty weeks to trim")
            return
        self.doc.record(f"Trimmed {removed} empty week(s)")
        self.rebuild()

    def action_clear_day(self) -> None:
        anchor = self.require_selection()
        if anchor is None:
            return
        cell = self.cells.get(anchor)
        if cell is not None:
            cell.load("")
        self.calendar.clear(anchor)
        self.doc.record(f"Cleared {anchor.isoformat()}")
        self.mark_dirty()

    def action_theme(self, name: str) -> None:
        self.flush()
        self.doc.settings.theme = name
        self.palette = theme_module.get(name)
        self._build_styles()
        self._restyle_chrome()
        self.doc.record(f"Switched theme to {name}")
        self.rebuild()

    def _restyle_chrome(self) -> None:
        palette = self.palette
        self.configure(background=palette.page)
        self.title_label.configure(font=self.f_title)
        self.range_label.configure(font=self.f_subtitle)
        self.status.configure(font=self.f_status)
        for widget in (self.title_label, self.range_label):
            widget.configure(background=palette.header, foreground=palette.header_text)
        self.title_label.master.configure(background=palette.header)
        self.weekday_bar.configure(background=palette.page)
        self.canvas.configure(background=palette.page)
        self.grid_frame.configure(background=palette.page)
        self.status.configure(background=palette.page, foreground=palette.muted)

    def action_save(self) -> bool:
        """Write the plan. Returns whether it actually reached the disk.

        Every failure is reported: a save that quietly does nothing is worse
        than one that says why, because the work looks safe when it is not.
        """
        self.flush()
        try:
            path = config_module.save(self.doc)
        except Exception as exc:  # noqa: BLE001 - the user must hear about any of them
            messagebox.showerror(
                "Could not save",
                f"The plan was not written.\n\n{self.doc.path}\n\n{exc}",
                parent=self,
            )
            return False
        self.mark_saved()
        self.remember_plan()
        self.refresh_header()
        self.refresh_status(f"Saved to {path}")
        return True

    def action_save_as(self) -> bool:
        path = filedialog.asksaveasfilename(
            parent=self,
            title="Save trip calendar",
            defaultextension=".xml",
            filetypes=[("Trip calendar XML", "*.xml"), ("All files", "*.*")],
            initialdir=paths.ensure_config_dir(),
            initialfile=os.path.basename(self.doc.path) or paths.DEFAULT_PLAN_NAME,
        )
        if not path:
            return False
        self.doc.path = path
        return self.action_save()

    def action_open(self) -> None:
        if not self.confirm_discard():
            return
        path = filedialog.askopenfilename(
            parent=self,
            title="Open trip calendar",
            filetypes=[("Trip calendar XML", "*.xml"), ("All files", "*.*")],
            initialdir=paths.ensure_config_dir(),
        )
        if not path:
            return
        try:
            doc = config_module.load(path)
        except (config_module.ConfigError, OSError) as exc:
            messagebox.showerror("Could not open", str(exc), parent=self)
            return
        self.adopt(doc)

    def action_new(self) -> None:
        if not self.confirm_discard():
            return
        path = filedialog.asksaveasfilename(
            parent=self,
            title="New trip calendar",
            defaultextension=".xml",
            filetypes=[("Trip calendar XML", "*.xml"), ("All files", "*.*")],
            initialdir=paths.ensure_config_dir(),
            initialfile="new_trip.xml",
        )
        if not path:
            return
        doc = config_module.new_document(path)
        doc.record("Created a new plan")
        self.adopt(doc)
        self.action_save()  # the new plan exists on disk straight away

    def adopt(self, doc: config_module.Document) -> None:
        self.doc = doc
        self.palette = theme_module.get(doc.settings.theme)
        self.selected = None
        self.mark_saved()
        self.remember_plan()
        self._build_fonts()
        self._build_styles()
        self._restyle_chrome()
        self.rebuild()
        self.report_load_warnings(f"Opened {doc.path}")

    def report_load_warnings(self, otherwise: str = "") -> None:
        """Say what was odd about the file, without getting in the way."""
        if self.doc.warnings:
            self.refresh_status("; ".join(self.doc.warnings))
        elif otherwise:
            self.refresh_status(otherwise)

    def remember_plan(self) -> None:
        """Record this plan as the one to reopen next time the app starts."""
        self.state.remember(self.doc.path)
        self.save_app_state()

    def save_app_state(self) -> None:
        """Persist window and last-file state. Never blocks anything."""
        try:
            self.state.window = self.winfo_geometry()
        except tk.TclError:
            pass
        try:
            session_module.save(self.state)
        except OSError:
            pass  # a read-only config folder is not worth interrupting anyone over

    def action_export(self) -> None:
        if not imaging.available():
            messagebox.showerror("Image export unavailable", imaging.INSTALL_HINT, parent=self)
            return
        self.flush()
        suggested = os.path.splitext(os.path.basename(self.doc.path))[0] + ".jpg"
        path = filedialog.asksaveasfilename(
            parent=self,
            title="Save calendar as image",
            defaultextension=".jpg",
            filetypes=[("JPEG image", "*.jpg *.jpeg"), ("All files", "*.*")],
            initialdir=paths.app_dir(),
            initialfile=suggested,
        )
        if not path:
            return
        try:
            written = imaging.render(self.doc, path, selected=self.selected)
        except (imaging.ExportError, OSError) as exc:
            messagebox.showerror("Could not export", str(exc), parent=self)
            return
        self.refresh_status(f"Exported {os.path.basename(written)}")

    def action_settings(self) -> None:
        self.flush()
        SettingsDialog(self)

    def action_about(self) -> None:
        change = self.doc.last_change
        lines = [
            "Trip Calendar",
            f"Version {__version__}",
            f"Built {BUILD_TIMESTAMP}",
            "",
            f"File: {self.doc.path}",
            f"Config folder: {paths.config_dir()}",
            f"Revision: {self.doc.revision}",
            f"Last saved: {self.doc.saved_at or 'never'}",
        ]
        if change:
            lines.append(f"Last change: {change.summary} ({change.at})")
        messagebox.showinfo("About", "\n".join(lines), parent=self)

    # -------------------------------------------------------------- close

    def confirm_discard(self) -> bool:
        """Ask about unsaved work. False means "stay where you are"."""
        self.flush()  # the check reads the model, so the boxes must be in it first
        if not self.is_dirty():
            return True
        answer = messagebox.askyesnocancel(
            "Unsaved changes",
            f"Save changes to this plan before continuing?\n\n{self.doc.path}",
            parent=self,
        )
        if answer is None:  # Cancel
            return False
        if answer and not self.action_save():
            # The save failed and has already said why. Let them decide whether
            # to carry on and lose the changes, rather than trapping them.
            return messagebox.askokcancel(
                "Continue without saving?",
                "The plan could not be saved. Continue anyway and lose the "
                "changes made since the last save?",
                icon="warning",
                default=messagebox.CANCEL,
                parent=self,
            )
        return True

    def on_close(self) -> None:
        """Close the window. Only an explicit Cancel keeps it open.

        Anything that goes wrong on the way out is reported and then ignored:
        a failure to tidy up must never leave the user with a window they
        cannot close.
        """
        try:
            self.flush()
        except Exception:  # noqa: BLE001
            traceback.print_exc()
        try:
            if not self.confirm_discard():
                return  # the only path that keeps the window open
        except Exception:  # noqa: BLE001 - a broken prompt must not trap anyone
            traceback.print_exc()
        try:
            self.save_app_state()
        except Exception:  # noqa: BLE001
            traceback.print_exc()
        self.shutdown()

    def shutdown(self) -> None:
        try:
            self.destroy()
        except tk.TclError:  # pragma: no cover - already torn down
            pass
        try:
            self.quit()  # belt and braces: leave the mainloop even if destroy failed
        except tk.TclError:  # pragma: no cover
            pass


class SettingsDialog(tk.Toplevel):
    """Edit the range and appearance that live in the XML file."""

    def __init__(self, app: TripCalendarApp) -> None:
        super().__init__(app)
        self.app = app
        palette = app.palette
        settings = app.doc.settings

        self.title("Calendar settings")
        self.configure(background=palette.page, padx=18, pady=16)
        self.resizable(False, False)
        self.transient(app)
        self.grab_set()

        self.vars = {
            "title": tk.StringVar(value=settings.title),
            "start": tk.StringVar(value=app.calendar.start.isoformat()),
            "end": tk.StringVar(value=app.calendar.end.isoformat()),
            "first_day": tk.StringVar(value=settings.first_day),
            "theme": tk.StringVar(value=settings.theme),
            "date_format": tk.StringVar(value=settings.date_format),
            "cell_width": tk.StringVar(value=str(settings.cell_width)),
            "cell_height": tk.StringVar(value=str(settings.cell_height)),
            "font_scale": tk.StringVar(value=f"{settings.font_scale:g}"),
        }

        rows = [
            ("Trip title", "title", None),
            ("Start week (any date in it)", "start", None),
            ("End week (any date in it)", "end", None),
            ("First day of week", "first_day", (SUNDAY, MONDAY)),
            ("Theme", "theme", tuple(theme_module.PALETTES)),
            ("Date format", "date_format", None),
            ("Day width (px)", "cell_width", None),
            ("Day height (px)", "cell_height", None),
            ("Font scale", "font_scale", None),
        ]
        for row, (label, key, choices) in enumerate(rows):
            tk.Label(
                self,
                text=label,
                background=palette.page,
                foreground=palette.text,
                font=app.f_subtitle,
                anchor="w",
            ).grid(row=row, column=0, sticky="w", pady=4, padx=(0, 14))
            if choices:
                widget = ttk.Combobox(
                    self,
                    textvariable=self.vars[key],
                    values=list(choices),
                    state="readonly",
                    width=24,
                )
            else:
                widget = ttk.Entry(self, textvariable=self.vars[key], width=26)
            widget.grid(row=row, column=1, sticky="ew", pady=4)

        buttons = ttk.Frame(self, style="Toolbar.TFrame")
        buttons.grid(row=len(rows), column=0, columnspan=2, sticky="e", pady=(16, 0))
        ttk.Button(buttons, text="Cancel", style="Tool.TButton", command=self.destroy).pack(
            side="left", padx=(0, 8)
        )
        ttk.Button(buttons, text="Apply", style="Accent.TButton", command=self.apply).pack(
            side="left"
        )

        self.bind("<Return>", lambda _e: self.apply())
        self.bind("<Escape>", lambda _e: self.destroy())

    def apply(self) -> None:
        app, settings, cal = self.app, self.app.doc.settings, self.app.calendar
        try:
            start = date.fromisoformat(self.vars["start"].get().strip())
            end = date.fromisoformat(self.vars["end"].get().strip())
        except ValueError:
            messagebox.showerror(
                "Check the dates",
                "Start and end week must be ISO dates, for example 2023-02-26.",
                parent=self,
            )
            return
        if end < start:
            messagebox.showerror("Check the dates", "The end week is before the start week.", parent=self)
            return

        settings.title = self.vars["title"].get().strip() or settings.title
        settings.date_format = self.vars["date_format"].get().strip() or settings.date_format
        for key, cast, attr in (
            ("cell_width", int, "cell_width"),
            ("cell_height", int, "cell_height"),
            ("font_scale", float, "font_scale"),
        ):
            try:
                setattr(settings, attr, cast(self.vars[key].get()))
            except ValueError:
                pass

        cal.set_first_day(self.vars["first_day"].get())
        cal.start, cal.end = start, end
        cal.normalise()
        grown = cal.grow_to_fit()

        theme_name = self.vars["theme"].get()
        settings.theme = theme_name
        app.palette = theme_module.get(theme_name)

        app.doc.record(
            f"Settings updated: {cal.start.isoformat()} → {cal.end.isoformat()}, "
            f"week starts {cal.first_day}, theme {theme_name}"
        )
        app._build_fonts()
        app._build_styles()
        app._restyle_chrome()
        app.rebuild()
        if grown:
            app.refresh_status(f"Range grown by {grown} week(s) to keep existing text visible")
        self.destroy()


def run(
    doc: config_module.Document, state: session_module.AppState | None = None
) -> None:
    TripCalendarApp(doc, state).mainloop()
