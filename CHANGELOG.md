# Changelog

Every release records its version number and the timestamp of the change.
The application writes the same pair into each saved plan (`appVersion`,
`savedAt`, `revision`) and keeps a per-document `<history>` of edits, so a plan
always says which version last touched it and when.

## 1.1.0 — 2026-09-06T21:15:00+00:00

- **New export: a text message summary.** One line per day, short enough to
  paste into a chat:

      day 1 - Flight to Dubrovnik + tour
      day 2 - Kravica waterfall + Mostar

  The opening lines of each day are joined into one, lines below them are
  dropped, and housekeeping lines ("Sleep: Kyoto") are passed over rather than
  spent as one of the kept lines. Day numbers count from the first day with
  anything written on it. **Text message** opens a preview that can be edited
  before sending, with Copy and Save as .txt, a character count, and controls
  for how many lines per day to keep, whether to show the title line, and
  whether to show dates.
- From the command line: `--message` prints the summary, `--message FILE.txt`
  writes it, and `--message-lines N` sets how much of each day to keep.
- No change to the XML format: the message options are chosen per export rather
  than stored in the plan.

## 1.0.4 — 2026-09-06T20:50:00+00:00

- **Application keyboard shortcuts removed.** Ctrl+Left and Ctrl+Right were
  bound application-wide to the day shifts, which took word-by-word cursor
  movement away from the day boxes and let one keystroke while typing
  restructure the trip. Ctrl+S, Ctrl+E and Ctrl+O are gone with them, and the
  menu accelerator labels along with them. Every command remains on a button or
  in the menus.
- The day boxes keep their own editing keys — Ctrl+Z, Ctrl+C/X/V, Ctrl+arrow
  word movement, Home and End — which now behave exactly as the platform
  intends.

## 1.0.3 — 2026-09-06T20:35:00+00:00

- **Day boxes are a fixed size.** They no longer grow as you type. A day with
  more text than fits gets a slim scrollbar and scrolls on its own; reaching
  either end hands the wheel back to the page, so one continuous scroll never
  gets stuck inside a box. Size is set by `cellHeight` in the settings.
- **Opening and saving an older file loses nothing.** Settings, whole sections
  and root attributes this version does not recognise are carried through to
  the next save untouched, so no format change here can strip anything out of
  an existing plan. A window position saved by 1.0.0 or 1.0.1 inside the plan
  is still honoured when there is no `config/app_state.xml` yet.
- Loading is more forgiving: a missing `<settings>` section falls back to
  defaults, a single unreadable `<day>` is skipped rather than failing the whole
  file, and a file from a newer schema opens with a note instead of an error.
  Anything odd is reported in the status bar.

## 1.0.2 — 2026-09-06T20:10:00+00:00

Fixes for faults found running the app on Windows.

- **The window would not close.** Closing is now blockable only by choosing
  Cancel at the unsaved-changes prompt. Anything that fails while shutting down
  is reported and then ignored rather than trapping the user in the window, and
  unexpected errors in any button now raise a dialog instead of vanishing into a
  console nobody is watching.
- **Saved plans went missing.** Files were written relative to the working
  directory, which is not the project folder when the app is launched from
  Explorer or an IDE. Plans now live in a `config` folder beside the
  application, and the status bar reports the full path a save went to.
- **"Save" did not clear the unsaved-changes prompt.** Whether there is unsaved
  work is now derived by comparing the plan against what was last written,
  instead of a flag that queued widget events could leave stuck on.
- **The app now reopens the last plan you had open.** Window geometry and the
  last-opened file moved to `config/app_state.xml`, so moving the window is no
  longer treated as an edit to the trip.
- There is always a config file in use: it is created on first run, so Save
  always has somewhere to go.
- The sample trip moved to `config/example_trip.xml`.

## 1.0.1 — 2026-09-06T19:45:00+00:00

- `requirements.txt` now spells out the full runtime dependency set and how to
  get tkinter on each platform; `requirements-dev.txt` added for tooling.
- README gained a copy-paste quick start and a worked example that walks a real
  day-shift through the sample trip.
- The walkthrough is covered by tests, so the documented steps cannot drift from
  what the code actually does.

## 1.0.0 — 2026-09-06T00:00:00+00:00

First release.

- Week-per-row calendar grid; every row is one week running left to right,
  starting on Sunday (Monday selectable).
- Every day is an editable text box; rows grow to fit the wordiest day.
- **Move Left / Move Right**: the selected day and every day after it slide one
  day earlier or later. A forward shift that would push text past the end of the
  range appends a week instead of dropping it; a backward shift from the first
  visible day prepends one. A backward shift that would overwrite text on the
  preceding day asks before doing it.
- Displayed range configured in XML (`startWeek` / `endWeek`), or from the
  in-app settings dialog; any date inside the wanted week will do.
- Save the whole plan — settings, day text and change history — to XML.
- Export the calendar to a JPG, drawn from the model so the image does not
  depend on window size or scroll position.
- Two themes (`aurora`, `midnight`), adjustable cell size and font scale.
- Command line: `--export FILE.jpg` renders headlessly; `--version` prints the
  version and build timestamp.
