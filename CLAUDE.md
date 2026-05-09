# CLAUDE.md

Personal CLI tool for planning DOK.fest München film viewings: scrape screenings from film pages, build a conflict-free personal schedule with interactive conflict resolution, export as markdown + ICS.

## Architecture

Single-file script `scrape_screenings.py` with sections:

1. **Parsing** — `parse(html)` extracts film title, duration, and screening details from festival HTML
2. **Scheduling** — `cp_sat_schedule()` using OR-Tools CP-SAT solver, `interactive_resolve()` for conflict resolution via `simple-term-menu`
3. **Output** — `format_table()`, `format_schedule()`, `write_ics()` produce markdown and ICS files

## Key constraints

- **Festival HTML lists screenings twice** — dedup by ICS URL, not by (date, time, venue)
- **`requests` needs a browser User-Agent** — the `HEADERS` constant provides one
- **ICS files are fetched from the festival** — we merge official `/ics/view/<N>` files, not generate our own
- **#NurImKino tag** — films with `a[href*="films_tag"]` containing "nur im kino" are marked; shown during conflict resolution to help prioritize cinema-only films

## Usage

```bash
docker build -t dokfest .
docker run --rm -it -v "$PWD:/data" dokfest filme.txt
```

Reads `filme.txt`, writes `filme.md` + `filme.ics`.

## Files

- `scrape_screenings.py` — the script
- `requirements.txt` — `requests`, `beautifulsoup4`, `ortools`, `simple-term-menu`
- `Dockerfile` — Python 3.13-slim with deps
- `README.md` — user docs
