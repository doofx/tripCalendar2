# Trip Calendar

A desktop trip planner: one row per week, one editable text box per day, and a
pair of buttons that slide the rest of the trip forward or back a day when plans
move. Written in Python with tkinter, so it runs on the standard library alone.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ Japan, Spring 2023                        26/02/2023 – 01/04/2023        │
├────────┬────────┬────────┬────────┬────────┬────────┬────────────────────┤
│  SUN   │  MON   │  TUE   │  WED   │  THU   │  FRI   │  SAT               │
├────────┼────────┼────────┼────────┼────────┼────────┼────────────────────┤
│ 26 Feb │ 27 Feb │ 28 Feb │ 01 Mar │ 02 Mar │ 03 Mar │ 04 Mar             │
│        │        │ Flight │ Tokyo, │ Going  │ Osaka  │ Osaka              │
│        │        │ to     │ land   │ to     │ Sleep: │ Send luggage       │
│        │        │ Tokyo  │ 19:10  │ Osaka  │ Osaka  │ to Kyoto           │
└────────┴────────┴────────┴────────┴────────┴────────┴────────────────────┘
```

## Quick start

Requires **Python 3.9 or newer** (3.11+ recommended).

```bash
git clone https://github.com/doofx/tripCalendar2.git
cd tripCalendar2

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -r requirements.txt
python main.py config/example_trip.xml
```

The window opens on the bundled Japan itinerary: five weeks, Sunday in the first
column, every day an editable box.

### tkinter

The GUI uses tkinter, which is part of the standard library — but on Linux it is
packaged separately, so install it with the system package manager rather than
pip:

```bash
sudo apt install python3-tk        # Debian / Ubuntu / Mint
sudo dnf install python3-tkinter   # Fedora / RHEL
sudo pacman -S tk                  # Arch
```

Windows and macOS get it from the python.org installer. Check with:

```bash
python -c "import tkinter; print(tkinter.TkVersion)"
```

## Worked example

Start from the sample trip and move a day:

```bash
python main.py config/example_trip.xml
```

1. **Type a plan.** Click 10 March — "Going to Matsumoto" — and add a line. The
   box stays the same size; if you outrun it, it scrolls.
2. **Tighten the range.** Click **Trim empty weeks**. The blank week after the
   flight home disappears, leaving four weeks ending 25 March.
3. **Absorb a delay.** Kyoto needs one more night. Click **09 March**, then
   **Move Right ▶**. 09 March empties out and everything from Arashiyama onward
   slides one day later — including the landing on 25 March, which now falls on
   26 March. That is past the end of the range, so a fifth week is appended to
   hold it rather than dropping the day.
4. **Change your mind.** The Arashiyama text now sits on 10 March. Select it and
   click **◀ Move Left** to pull the whole tail back where it was. Had the day
   before held text, you would be asked before it was overwritten.
5. **Save.** **Save** writes the plan back to `config/example_trip.xml`, stamped
   with the version, a new revision number and the time. The status bar shows
   all three, and the full path it went to.
6. **Export.** **Save as image**, or straight from the shell without opening a
   window:

```bash
python main.py config/example_trip.xml --export japan.jpg --scale 3
# Wrote japan.jpg
```

Starting a trip of your own:

```bash
cp config/example_trip.xml config/my_trip.xml
python main.py my_trip.xml            # a bare name means config/my_trip.xml
```

Opening a path that does not exist starts an empty four-week calendar beginning
this week; set the real dates under **Settings**, or edit `startWeek` and
`endWeek` in the file. Running `python main.py` with no arguments reopens the
plan you had open last, falling back to `config/trip_calendar.xml`.

Other command-line options:

```bash
python main.py --help              # all options
python main.py --version           # version and build timestamp
```

## Features

**A week per row.** Every row is a full week running left to right. The first
column is Sunday by default; set `firstDayOfWeek` to `monday` if you prefer. The
range always snaps to whole weeks so the grid stays rectangular.

**Every day is a text box.** Click a day and type. Boxes are a fixed size and
stay that way — the grid never reflows while you are working in it. A day with
more text than fits grows a slim scrollbar and scrolls on its own; reaching the
top or bottom of a day hands the wheel back to the page, so one continuous
scroll never gets trapped inside a box. `cellHeight` in the settings sets how
tall a day is.

**Move Left / Move Right.** This is the point of the app. Select a day, then:

- **Move Right** — the selected day and everything after it move one day later.
  The selected day is left blank, which is how you absorb an extra night
  somewhere. If that would push text past the end of the displayed range, a week
  is appended rather than losing the day.
- **Move Left** — the selected day and everything after it move one day earlier,
  closing up a day you decided to skip. If the selected day is the first one on
  display, a week is prepended to make room. If the day before it already has
  text, that text would be destroyed, so you are asked to confirm first.

Nothing is ever silently dropped in either direction.

**Save as image.** *Save as image* writes a JPG. The image is drawn from the plan
rather than screen-grabbed, so it always contains the whole calendar at full
resolution regardless of the window size or where you had scrolled to — and
unlike the on-screen grid it grows each row to fit, so text you would have had
to scroll for is all visible in the exported image. The same
render is available headlessly:

```bash
python main.py config/example_trip.xml --export japan.jpg --scale 3
```

**Everything persists.** *Save* writes the range, the look and feel, the text of
every day and the change history back to the XML file, and the status bar tells
you the full path it went to.

Files live in a `config` folder next to the application, never in whatever
directory the app happened to be started from — so a saved plan is always
somewhere you can find it again. There is always a config file in use:
`config/trip_calendar.xml` is created on the first run, so *Save* always has a
destination.

Starting the app with no arguments reopens **the last plan you had open**. That
choice, and the window position, live in `config/app_state.xml`, separately from
the trip itself — moving the window is not an edit to your plan, so it never
makes the app ask whether you want to save.

**Version and timestamp of every change.** Each save stamps the file with the
application version, the wall-clock time and a revision counter, and appends a
one-line record of what changed to a rolling `<history>` block. The status bar
and *Help → About* show the same information, and it is printed along the bottom
of every exported image.

## The XML file

One human-editable file holds the entire plan. `startWeek` and `endWeek` are any
date inside the first and last week you want on screen — they are snapped to week
boundaries when loaded, so you do not have to look up which day was a Sunday.

```xml
<?xml version="1.0" encoding="utf-8"?>
<tripCalendar schemaVersion="1" appVersion="1.0.0" revision="4"
              savedAt="2026-09-06T18:20:11+00:00">
  <settings>
    <startWeek>2023-02-26</startWeek>     <!-- first week shown -->
    <endWeek>2023-04-01</endWeek>         <!-- last week shown  -->
    <firstDayOfWeek>sunday</firstDayOfWeek>
    <title>Japan, Spring 2023</title>
    <theme>aurora</theme>                 <!-- aurora | midnight -->
    <dateFormat>%d/%m/%Y</dateFormat>
    <cellWidth>168</cellWidth>
    <cellHeight>132</cellHeight>
    <fontScale>1</fontScale>
  </settings>
  <days>
    <day date="2023-02-28">Flight to Tokyo at 20:00</day>
    <day date="2023-03-01">Tokyo, land at 19:10
Sleep: Tokyo</day>
  </days>
  <history>
    <change revision="4" at="2026-09-06T18:20:11+00:00" version="1.0.0">
      Moved 2023-03-10 and later one day forward; added 1 week at the end
    </change>
  </history>
</tripCalendar>
```

If a `<day>` falls outside `startWeek`–`endWeek`, the range is widened on load so
that text is never hidden.

### Files from older versions

Opening and saving an existing plan never loses anything. Settings, whole
sections and root attributes that this version does not recognise are carried
through to the next save exactly as they were found, so upgrading cannot strip
material out of a file — and a plan written here stays readable by an older
build. A window position saved by 1.0.0 or 1.0.1 inside the plan is still
honoured until `config/app_state.xml` takes over.

Loading is deliberately forgiving: a missing `<settings>` section falls back to
defaults, one unreadable `<day>` is skipped rather than failing the whole file,
and a file from a newer schema opens with a note in the status bar rather than
an error.

## Keyboard

The application claims **no keyboard shortcuts of its own**. Every command is on
a button or in the menus, so nothing can be triggered by a stray keystroke while
you are typing into a day — a mistyped `Ctrl+←` restructuring the whole trip is
a lot of damage for one key.

That leaves the keyboard to the day boxes, where the usual editing keys work as
your platform intends:

| Key | Action inside a day |
| --- | --- |
| `Ctrl` + `←` / `→` | Move the cursor a word at a time |
| `Ctrl` + `Z` / `Y` | Undo / redo |
| `Ctrl` + `C` / `X` / `V` | Copy, cut, paste |
| `Home` / `End` | Start and end of the line |
| `Tab` | Move to the next day |

## Layout

| Path | What it holds |
| --- | --- |
| `main.py` | Entry point and command line |
| `tripcalendar/model.py` | The calendar: weeks, day text, the shift operations |
| `tripcalendar/config.py` | XML load and save, settings, change history |
| `tripcalendar/ui.py` | The tkinter window |
| `tripcalendar/imaging.py` | JPG rendering |
| `tripcalendar/theme.py` | Palettes shared by the window and the export |
| `tripcalendar/version.py` | Version number and build timestamp |
| `tripcalendar/paths.py` | Where the config folder is |
| `tripcalendar/session.py` | Last-opened plan and window position |
| `config/example_trip.xml` | A sample trip to open |
| `config/trip_calendar.xml` | Your plan, created on first run |
| `config/app_state.xml` | Which plan to reopen, and where the window was |
| `requirements.txt` | Runtime dependencies |
| `requirements-dev.txt` | Test and lint tooling |
| `tests/` | Unit tests for the model, the XML layer and text layout |

## Tests

```bash
python -m unittest discover -s tests -v
```

The tests cover the parts that do not need a display: week geometry, both shift
directions and their edge cases, XML round-tripping, and text wrapping. The
image-rendering test is skipped when Pillow is not installed.
