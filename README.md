# dokfest-scheduler

Scrape film screenings from [DOK.fest München](https://www.dokfest-muenchen.de/) film pages, build a conflict-free personal viewing schedule, and export it as an ICS calendar file.

## What it does

Given a list of film page URLs (e.g. `https://www.dokfest-muenchen.de/films/intelligence-rising`), the script:

1. Fetches each page, deduplicates the screening list (which appears in both sidebar and main column on the festival site), and emits a markdown table of all screenings — film title, date, time, venue, duration, festival ICS link, and any Q&A note.
2. Optionally builds a **personal viewing schedule**: picks one screening per film such that no two picked screenings overlap (with a configurable buffer for travel time).
3. Optionally writes an **ICS calendar file** of that schedule for import into Google Calendar, Apple Calendar, Outlook, etc.

If a conflict-free schedule covering every film isn't possible, the script falls back to picking the largest subset that fits and lists the films that had to be dropped.

## Quick start (Docker — recommended)

The Docker path avoids native-library issues (notably on NixOS, where pre-built numpy/ortools wheels fail to load `libstdc++.so.6`).

```bash
docker build -t dokfest .

# urls.txt: one film page URL per line
cat urls.txt | docker run --rm -i -v "$PWD:/out" dokfest \
    --schedule --ics /out/schedule.ics > schedule.md
```

The `-v "$PWD:/out"` mount is what lets the container's `/out/schedule.ics` land as `./schedule.ics` on the host.

## Local install (no Docker)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
./scrape_screenings.py --schedule --ics schedule.ics < urls.txt > schedule.md
```

If `ortools` fails to install or import on your machine, the script automatically falls back to a pure-Python backtracking solver (slower on hard instances — see [Performance](#performance) below).

## Usage

```
scrape_screenings.py [--schedule] [--ics PATH] [--no-table]
                     [--buffer MINUTES] [--solver {auto,cpsat,backtrack}]
                     [--workers N] [URL ...]
```

URLs come from positional args **or** stdin, one per line. Stdin form is preferred for 20–30 films.

| Flag | Effect |
|---|---|
| `--schedule` | also build a personal viewing schedule |
| `--ics PATH` | write schedule as ICS calendar (requires `--schedule`) |
| `--no-table` | skip the markdown table; useful with `--schedule --ics` |
| `--buffer N` | minutes between screenings (default 15) — covers travel + entry |
| `--solver` | `auto` (default), `cpsat`, or `backtrack` |
| `--workers N` | CP-SAT search workers (default 1; rarely needed) |

### Examples

```bash
# Just the markdown table
./scrape_screenings.py < urls.txt > screenings.md

# Schedule + ICS, with a 30-min buffer (you cycle slowly)
./scrape_screenings.py --schedule --buffer 30 --ics schedule.ics < urls.txt > schedule.md

# Only the schedule, no table (good for piping)
./scrape_screenings.py --schedule --no-table --ics schedule.ics < urls.txt
```

## Output formats

- **Markdown table** (stdout): one row per screening, sorted by film. Columns: Film, Date, Time, Venue, Duration, ICS, Comment.
- **Schedule** (stdout, with `--schedule`): chronological, grouped by date. Films that couldn't be scheduled are listed at the end.
- **ICS file** (`--ics PATH`): RFC 5545 compliant. Times in UTC (converted from Munich local). Each event has SUMMARY (title), LOCATION (venue), DTSTART/DTEND, and DESCRIPTION (length + comment + festival source URL). UIDs derived from the festival's own ICS endpoint IDs, so re-importing won't duplicate events.

## Performance

The scheduling problem is "pick one screening per film, no time conflicts" — equivalent to a constrained max-coverage problem. With `ortools` installed (default), CP-SAT solves 30-film instances in ~20 ms. The pure-Python backtracking fallback can take seconds-to-minutes or fail to terminate on the same input.

Measured on synthetic 30-film instances:

| | backtracking | CP-SAT (1 worker) |
|---|---|---|
| typical | ~5 s | ~20 ms |
| hard instance | timeout (>30 s) | ~20 ms |

Increasing `--workers` rarely helps at this problem size — orchestration overhead dominates the gains. CP-SAT on 1 core already beats backtracking on 8 cores by orders of magnitude.

## Troubleshooting

- **`ImportError: libstdc++.so.6: cannot open shared object file`** (typical on NixOS): pip-installed numpy/ortools wheels expect FHS library paths. Use Docker, or set `LD_LIBRARY_PATH=/path/to/gcc-libs/lib` (e.g. via a `shell.nix`).
- **`✗ --solver cpsat requested but 'ortools' is not installed`**: either install ortools, or omit `--solver cpsat` to fall back to backtracking.
- **403 from the festival site**: the script sets a Chrome-on-Linux User-Agent. The default Python `requests` UA is rejected.
- **Schedule drops films you wanted**: increase candidate screenings (more film URLs), reduce `--buffer`, or accept the dropped films — the solver returns the *optimal* maximum-coverage schedule, so dropped films genuinely don't fit.

## Files

- `scrape_screenings.py` — single-file script (parsing, scheduling, ICS output, CLI)
- `requirements.txt` — `requests`, `beautifulsoup4`, `ortools`
- `Dockerfile` — Debian-slim Python 3.13 base + libstdc++/libgomp + pip deps
- `CLAUDE.md` — context for Claude Code sessions
