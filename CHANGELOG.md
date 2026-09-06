# Changelog

Every release records its version number and the timestamp of the change.
The application writes the same pair into each saved plan (`appVersion`,
`savedAt`, `revision`) and keeps a per-document `<history>` of edits, so a plan
always says which version last touched it and when.

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
