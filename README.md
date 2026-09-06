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

## Running it

```bash
python main.py                      # opens trip_calendar.xml, or starts a fresh month
python main.py example_trip.xml     # opens the bundled sample trip
```

tkinter comes with Python on the python.org installers for Windows and macOS. On
Linux it is a separate package:

```bash
sudo apt install python3-tk      # Debian / Ubuntu
sudo dnf install python3-tkinter # Fedora
```

Saving the calendar as an image needs Pillow:

```bash
pip install -r requirements.txt
```

## Features

**A week per row.** Every row is a full week running left to right. The first
column is Sunday by default; set `firstDayOfWeek` to `monday` if you prefer. The
range always snaps to whole weeks so the grid stays rectangular.

**Every day is a text box.** Click a day and type. Rows grow to fit the wordiest
day in the week, so nothing gets clipped as the plan fills up.

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
resolution regardless of the window size or where you had scrolled to. The same
render is available headlessly:

```bash
python main.py example_trip.xml --export japan.jpg --scale 3
```

**Everything persists.** *Save* writes the range, the look and feel, the text of
every day and the change history back to the XML file. Window geometry is saved
on exit, so the app reopens the way you left it.

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
    <window>1360x880+120+60</window>
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

## Keyboard

| Shortcut | Action |
| --- | --- |
| `Ctrl` + `S` | Save |
| `Ctrl` + `E` | Export as JPG |
| `Ctrl` + `O` | Open |
| `Ctrl` + `←` | Move the selected day and later days one day earlier |
| `Ctrl` + `→` | Move the selected day and later days one day later |
| `Ctrl` + `Z` | Undo, within the focused day |

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
| `example_trip.xml` | A sample trip to open |
| `tests/` | Unit tests for the model, the XML layer and text layout |

## Tests

```bash
python -m unittest discover -s tests -v
```

The tests cover the parts that do not need a display: week geometry, both shift
directions and their edge cases, XML round-tripping, and text wrapping. The
image-rendering test is skipped when Pillow is not installed.
