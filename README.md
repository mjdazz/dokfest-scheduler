# dokfest-scheduler

Build a personal viewing schedule for [DOK.fest München](https://www.dokfest-muenchen.de/).

## Usage

```bash
docker build -t dokfest .
docker run --rm -it -v "$PWD:/data" dokfest filme.txt
```

This reads film URLs from `filme.txt` (one per line), scrapes screening times, and writes:
- `filme.md` — markdown table of all screenings + your personal schedule
- `filme.ics` — calendar file for import into Google Calendar / Apple Calendar / Outlook

If not all films fit due to time conflicts, a menu lets you choose which films to keep.

## Options

| Flag | Effect |
|---|---|
| `--buffer N` | minutes between screenings (default 15) |

Example with 30-minute buffer:

```bash
docker run --rm -it -v "$PWD:/data" dokfest filme.txt --buffer 30
```

## Troubleshooting

- **403 from the festival site** — the script sets a browser User-Agent, but the site may still block some IPs
- **Menu not appearing** — make sure you're using `-it` flags for interactive mode
