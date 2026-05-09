# CLAUDE.md

Personal CLI tool for planning DOK.fest München film viewings: scrape screenings from film pages, build a conflict-free personal schedule, export as ICS.

## Architecture

Single-file script `scrape_screenings.py` divided into clearly labelled sections (search the file for the `─────` banners):

1. **Parsing** — `parse(html)` over BeautifulSoup. Extracts film title from `<h1>`, duration from `<h2>` (regex on `Länge: X min.`), and per-screening date/time/venue/comment/ICS-URL from `.eventdate li` blocks.
2. **Scheduling** — `cp_sat_schedule()` using Google OR-Tools CP-SAT solver. Operates on a `{film_name: [screening_dict, ...]}` mapping.
3. **ICS output** — `write_ics(picked, path)` emits RFC 5545. Helpers `ics_escape()` and `ics_fold()` handle the format's quirks.
4. **`main()`** — argparse, scrape loop, dispatch to scheduler, emit table/schedule/ICS.

## Key constraints (don't relearn these)

- **The festival HTML lists each screening twice** — once in the sidebar (`films-sidebar`) and once in the main column (`hide-on-tablet` block). Both have the same `/ics/view/<id>` URL. Dedup by ICS URL; do not dedup by `(date, time, venue)`.
- **`requests` default User-Agent gets a 403.** The `HEADERS` constant sets a Chrome-on-Linux UA. Don't remove it.
- **Festival times are Munich local (Europe/Berlin).** ICS output converts to UTC. Don't change this without checking what calendar apps do with floating times.
- **CP-SAT is the only solver** and `ortools` is a hard dependency. It solves 30-film instances in ~20 ms. Do not replace with pure-Python alternatives — they would be orders of magnitude slower.
- **Stable ICS UIDs** are derived from the festival's `/ics/view/<N>` endpoint ID. Re-importing the calendar after a re-run shouldn't duplicate events. Don't generate UIDs from `uuid4()` or timestamps.

## Conventions

- **Output streaming**: the markdown table is printed row-by-row as URLs are scraped, so partial output survives interruption. Don't refactor to buffer everything before printing.
- **Per-URL error tolerance**: a single failing URL logs to stderr and the run continues. Don't `raise` on individual scrape failures.
- **Defensive parsing**: `parse_datetime` returns `None` on malformed input; `parse_duration_from_h2` returns `None` if the regex misses; the scheduler skips screenings with `start is None`. Preserve this — real-world HTML breaks.

## Commands

```bash
# Build & run via Docker (preferred — works on NixOS where native pip wheels don't)
docker build -t dokfest .
cat urls.txt | docker run --rm -i -v "$PWD:/out" dokfest --schedule --ics /out/schedule.ics > schedule.md

# Local (assumes a working venv with ortools)
./scrape_screenings.py --schedule --ics schedule.ics < urls.txt > schedule.md
```

There are no automated tests. Verification has been done interactively against a fixture file containing the relevant HTML structure (h1, h2 with `Länge:`, two `.eventdate ul` blocks). When changing the parser, validate against that pattern before claiming it works.

## What's intentionally not here

- **Per-venue travel times.** Buffer is a flat `--buffer` value (default 15 min). Real Munich-venue travel times vary 5–40 min. If the user asks to improve scheduling realism, this is the obvious next step.
- **Film priorities.** The solver treats all films as equally must-see. Adding weights would be a one-line change in the CP-SAT objective.
- **State between runs.** Every run re-scrapes. There's no caching layer. If the user wants this, consider `requests-cache` rather than rolling your own.
- **Tests.** Manual fixture-based verification only.

## Untested in any prior session

- **End-to-end run against the live festival site.** Prior sessions worked from a sandboxed environment that the dokfest server returns 403 to regardless of headers. Parsing was verified against pasted HTML; scheduling and ICS output against synthetic data. The first time this runs against real URLs may surface edge cases — particularly around date/time parsing if any film page uses non-standard formatting.
- **Calendar app import.** ICS output round-trips cleanly through the Python `icalendar` parser, but has not been imported into Google Calendar / Apple Calendar / Outlook. If a calendar app rejects the file, check for VTIMEZONE-related complaints first (we currently emit UTC without a VTIMEZONE block, which is RFC-compliant but some clients prefer TZID form).

## Files

- `scrape_screenings.py` — the script
- `requirements.txt` — `requests`, `beautifulsoup4`, `ortools`
- `Dockerfile` — Debian-slim Python 3.13, with `libstdc++6` + `libgomp1` apt-installed for ortools
- `README.md` — user-facing docs
