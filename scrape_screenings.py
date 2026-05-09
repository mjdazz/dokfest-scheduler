#!/usr/bin/env python3
"""
Scrape screening info from dokfest-muenchen.de film pages, optionally build a
personal viewing schedule (one screening per film, no time conflicts).

Usage:
    scrape_screenings.py URL [URL ...]
    cat urls.txt | scrape_screenings.py
    cat urls.txt | scrape_screenings.py --schedule
    cat urls.txt | scrape_screenings.py --schedule --no-table

Output: Markdown table + (optional) schedule on stdout. Progress + errors on stderr.
"""
import sys
import re
import time
import argparse
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
from urllib.parse import urljoin

BASE = "https://www.dokfest-muenchen.de"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}
DELAY = 0.5                # seconds between requests
DEFAULT_DURATION_MIN = 90  # used if "Länge: X min." can't be parsed
BUFFER_MIN = 15            # gap required between screenings (travel + entry)
TZ_MUNICH = ZoneInfo("Europe/Berlin")
TZ_UTC = ZoneInfo("UTC")


# ───────────────────────── parsing ─────────────────────────

def parse_duration_from_h2(h2_text):
    """Find 'Länge: X min.' in the h2 text. Returns minutes (int) or None."""
    m = re.search(r"Länge:\s*(\d+)\s*min", h2_text)
    return int(m.group(1)) if m else None

def parse_datetime(date_str, time_str):
    """'So., 10.05.26' + '18.00' → datetime(2026, 5, 10, 18, 0). Returns None on failure."""
    try:
        ds = date_str.split(",", 1)[1].strip() if "," in date_str else date_str.strip()
        return datetime.strptime(f"{ds} {time_str}", "%d.%m.%y %H.%M")
    except (ValueError, IndexError):
        return None

def parse(html):
    soup = BeautifulSoup(html, "html.parser")
    h1 = soup.find("h1")
    title = h1.get_text(strip=True) if h1 else "(unknown)"
    h2 = soup.find("h2")
    duration = parse_duration_from_h2(h2.get_text(" ", strip=True)) if h2 else None

    rows = []
    seen = set()
    for li in soup.select(".eventdate li"):
        ics = li.select_one('a[href^="/ics/view/"]')
        ev  = li.select_one('a[href^="events/view/"]')
        if not ics or not ev:
            continue
        ics_url = urljoin(BASE, ics["href"])
        if ics_url in seen:        # dedup: list appears in sidebar AND main column
            continue
        seen.add(ics_url)

        parts = [p.strip() for p in ev.get_text(separator="\n").split("\n") if p.strip()]
        date_str = parts[0] if len(parts) > 0 else ""
        time_str = parts[1] if len(parts) > 1 else ""
        venue    = parts[2] if len(parts) > 2 else ""
        comment_tag = li.select_one("p.comment")
        comment  = comment_tag.get_text(strip=True) if comment_tag else ""

        rows.append({
            "film":           title,
            "duration":       duration if duration is not None else DEFAULT_DURATION_MIN,
            "duration_known": duration is not None,
            "date_str":       date_str,
            "time_str":       time_str,
            "venue":          venue,
            "ics":            ics_url,
            "comment":        comment,
            "start":          parse_datetime(date_str, time_str),
        })
    return rows

def fetch(url):
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.text


# ───────────────────────── scheduling ─────────────────────────

def conflicts(a, b, buffer_min=None):
    """True if screenings a and b overlap (with buffer added to each)."""
    if buffer_min is None:
        buffer_min = BUFFER_MIN
    if a["start"] is None or b["start"] is None:
        return False
    a_end = a["start"] + timedelta(minutes=a["duration"] + buffer_min)
    b_end = b["start"] + timedelta(minutes=b["duration"] + buffer_min)
    return a["start"] < b_end and b["start"] < a_end

from ortools.sat.python import cp_model

# Optional TUI for interactive conflict resolution
try:
    from simple_term_menu import TerminalMenu
    HAVE_TUI = True
except ImportError:
    HAVE_TUI = False

def cp_sat_schedule(by_film, workers=1):
    """
    Solve max-coverage scheduling with CP-SAT.
    Returns the largest set of screenings (≤1 per film) with no time conflicts.
    If len(result) == len(by_film), every film was scheduled.
    """
    flat = []
    by_idx = {}
    for film, scrs in by_film.items():
        by_idx[film] = []
        for sc in scrs:
            if sc["start"] is None:
                continue
            by_idx[film].append(len(flat))
            flat.append(sc)

    m = cp_model.CpModel()
    x = [m.NewBoolVar(f"x{i}") for i in range(len(flat))]

    # at most one screening per film
    for idxs in by_idx.values():
        if idxs:
            m.Add(sum(x[i] for i in idxs) <= 1)

    # no time conflicts (with buffer)
    for i in range(len(flat)):
        for j in range(i + 1, len(flat)):
            if conflicts(flat[i], flat[j]):
                m.Add(x[i] + x[j] <= 1)

    m.Maximize(sum(x))

    solver = cp_model.CpSolver()
    if workers > 1:
        solver.parameters.num_search_workers = workers
    status = solver.Solve(m)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return []
    return [flat[i] for i in range(len(flat)) if solver.Value(x[i])]


def find_blocking_films(picked, by_film, excluded):
    """
    For each unpicked film, find which picked films block it.
    Returns: {unpicked_film: [(picked_screening, unpicked_screening), ...]}
    """
    picked_films = {s["film"] for s in picked}
    blocking = {}
    for film, screenings in by_film.items():
        if film in picked_films or film in excluded:
            continue
        blockers = []
        for scr in screenings:
            if scr["start"] is None:
                continue
            for p in picked:
                if conflicts(scr, p):
                    blockers.append((p, scr))
        if blockers:
            blocking[film] = blockers
    return blocking


def format_screening(s):
    """Format a screening for display: 'Film (Day HH:MM, Venue)'"""
    if s["start"]:
        return f"{s['film']} ({s['start'].strftime('%a %H:%M')}, {s['venue']})"
    return f"{s['film']} ({s['venue']})"


def interactive_resolve(by_film, initial_picked, names, workers=1):
    """
    Interactive TUI loop to resolve scheduling conflicts.
    Returns the final list of picked screenings.
    """
    import os

    # Handle piped stdin: open /dev/tty for interactive input
    tty_fd = None
    if not sys.stdin.isatty():
        try:
            tty_fd = os.open("/dev/tty", os.O_RDONLY)
            os.dup2(tty_fd, 0)  # redirect stdin to tty
        except OSError:
            print("⚠  Cannot open /dev/tty for interactive mode.", file=sys.stderr)
            return initial_picked

    picked = initial_picked
    excluded = set()

    try:
        while len(picked) < len(names) - len(excluded):
            blocking = find_blocking_films(picked, by_film, excluded)
            if not blocking:
                break

            # Find the unpicked film with fewest blocking conflicts (simplest choice)
            unpicked_film = min(blocking.keys(), key=lambda f: len(blocking[f]))
            blockers = blocking[unpicked_film]

            # Group by blocking film (a picked film may block via multiple screenings)
            blocking_films = {}
            for picked_scr, unpicked_scr in blockers:
                blocking_films.setdefault(picked_scr["film"], []).append((picked_scr, unpicked_scr))

            # If blocked by multiple films, pick the one with the "best" alternative
            blocking_film = list(blocking_films.keys())[0]
            picked_scr, unpicked_scr = blocking_films[blocking_film][0]

            n_scheduled = len(picked)
            n_total = len(names) - len(excluded)

            print(f"\n{'─' * 60}", file=sys.stderr)
            print(f"  Schedule: {n_scheduled} of {n_total} films", file=sys.stderr)
            print(f"  \"{unpicked_film}\" cannot be scheduled.", file=sys.stderr)
            print(f"  It conflicts with \"{blocking_film}\" (currently scheduled).", file=sys.stderr)
            print(f"{'─' * 60}\n", file=sys.stderr)

            options = [
                f"Keep \"{blocking_film}\" — skip \"{unpicked_film}\"",
                f"Keep \"{unpicked_film}\" — remove \"{blocking_film}\"",
                "Accept current schedule",
            ]

            menu = TerminalMenu(
                options,
                title="  What would you like to do?",
                menu_cursor_style=("fg_cyan", "bold"),
                menu_highlight_style=("bg_gray", "fg_black"),
            )
            choice = menu.show()

            if choice is None or choice == 2:  # quit or accept
                break
            elif choice == 0:  # keep current, skip unpicked
                excluded.add(unpicked_film)
                print(f"  → Skipping \"{unpicked_film}\"", file=sys.stderr)
            elif choice == 1:  # keep unpicked, remove picked
                excluded.add(blocking_film)
                print(f"  → Removing \"{blocking_film}\", re-solving...", file=sys.stderr)
                # Re-solve without the excluded films
                filtered = {f: s for f, s in by_film.items() if f not in excluded}
                picked = cp_sat_schedule(filtered, workers=workers)

        return picked

    finally:
        if tty_fd is not None:
            os.close(tty_fd)


# ───────────────────────── output ─────────────────────────

def md_row(cells):
    return "| " + " | ".join(str(c).replace("|", "\\|").replace("\n", " ") for c in cells) + " |"

def print_table(screenings):
    cols = ["Film", "Date", "Time", "Venue", "Duration", "ICS", "Comment"]
    print(md_row(cols))
    print("|" + "|".join(["---"] * len(cols)) + "|")
    for s in screenings:
        dur = f"{s['duration']} min" + ("" if s["duration_known"] else "*")
        print(md_row([s["film"], s["date_str"], s["time_str"], s["venue"],
                      dur, s["ics"], s["comment"]]))

def print_schedule(picked, all_film_names):
    print("\n## Personal schedule\n")
    last_date = None
    for s in sorted(picked, key=lambda x: x["start"]):
        d = s["start"].date()
        if d != last_date:
            print(f"\n### {s['start'].strftime('%a, %d %b %Y')}\n")
            last_date = d
        end = s["start"] + timedelta(minutes=s["duration"])
        line = (f"- **{s['start'].strftime('%H:%M')}–{end.strftime('%H:%M')}**  "
                f"_{s['venue']}_  —  {s['film']} ({s['duration']} min)")
        if s["comment"]:
            line += f"\n    - _{s['comment']}_"
        print(line)
    scheduled = {s["film"] for s in picked}
    missing = [f for f in all_film_names if f not in scheduled]
    if missing:
        print(f"\n### Not scheduled ({len(missing)})\n")
        for f in missing:
            print(f"- {f}")


# ───────────────────────── ICS output ─────────────────────────

def ics_escape(s):
    """Escape RFC 5545 TEXT special chars."""
    return (s.replace("\\", "\\\\")
             .replace(",", "\\,")
             .replace(";", "\\;")
             .replace("\n", "\\n"))

def ics_fold(line, limit=73):
    """Fold a content line per RFC 5545 §3.1 (75 octets, but 73 leaves room for CRLF)."""
    encoded = line.encode("utf-8")
    if len(encoded) <= limit:
        return line
    parts = []
    while len(encoded) > limit:
        cut = limit
        # don't split inside a multi-byte UTF-8 sequence
        while cut > 0 and (encoded[cut] & 0xC0) == 0x80:
            cut -= 1
        parts.append(encoded[:cut].decode("utf-8"))
        encoded = encoded[cut:]
    parts.append(encoded.decode("utf-8"))
    return "\r\n ".join(parts)

def write_ics(picked, path):
    """Write a minimal RFC 5545 ICS calendar with one VEVENT per scheduled screening."""
    now_stamp = datetime.now(tz=TZ_UTC).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//dokfest-planner//scrape_screenings//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]
    for s in sorted(picked, key=lambda x: x["start"]):
        # interpret naive datetime as Munich local time, emit as UTC
        start_utc = s["start"].replace(tzinfo=TZ_MUNICH).astimezone(TZ_UTC)
        end_utc   = start_utc + timedelta(minutes=s["duration"])
        # stable UID derived from the festival's own ICS URL (last path segment)
        uid = s["ics"].rsplit("/", 1)[-1] + "@dokfest-planner"
        desc = f"Länge: {s['duration']} min"
        if s.get("comment"):
            desc += f"\n{s['comment']}"
        desc += f"\nSource: {s['ics']}"
        lines.extend([
            "BEGIN:VEVENT",
            ics_fold(f"UID:{uid}"),
            f"DTSTAMP:{now_stamp}",
            f"DTSTART:{start_utc.strftime('%Y%m%dT%H%M%SZ')}",
            f"DTEND:{end_utc.strftime('%Y%m%dT%H%M%SZ')}",
            ics_fold(f"SUMMARY:{ics_escape(s['film'])}"),
            ics_fold(f"LOCATION:{ics_escape(s['venue'])}"),
            ics_fold(f"DESCRIPTION:{ics_escape(desc)}"),
            "END:VEVENT",
        ])
    lines.append("END:VCALENDAR")
    # newline="" prevents Python translating \r\n into \r\r\n on Windows hosts
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write("\r\n".join(lines) + "\r\n")


# ───────────────────────── main ─────────────────────────

def main():
    global BUFFER_MIN
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("urls", nargs="*", help="film page URLs (or pipe via stdin)")
    ap.add_argument("--schedule", action="store_true",
                    help="also build a personal viewing schedule")
    ap.add_argument("--no-table", action="store_true",
                    help="skip the screenings table (only emit the schedule)")
    ap.add_argument("--buffer", type=int, default=BUFFER_MIN,
                    help=f"minutes between screenings (default {BUFFER_MIN})")
    ap.add_argument("--workers", type=int, default=1,
                    help="CP-SAT search workers (default 1 — usually plenty)")
    ap.add_argument("--interactive", "-i", action="store_true",
                    help="interactive TUI to resolve conflicts when not all films fit")
    ap.add_argument("--ics", metavar="PATH",
                    help="also write the schedule as an ICS calendar file to PATH "
                         "(requires --schedule)")
    args = ap.parse_args()

    BUFFER_MIN = args.buffer

    urls = args.urls if args.urls else [l.strip() for l in sys.stdin if l.strip()]
    if not urls:
        ap.error("provide URLs as args or via stdin")

    all_screenings = []
    for i, url in enumerate(urls, 1):
        print(f"[{i}/{len(urls)}] {url}", file=sys.stderr)
        try:
            all_screenings.extend(parse(fetch(url)))
        except Exception as e:
            print(f"  ! error: {e}", file=sys.stderr)
        if i < len(urls):
            time.sleep(DELAY)

    # warn about missing durations
    if any(not s["duration_known"] for s in all_screenings):
        n = sum(1 for s in all_screenings if not s["duration_known"])
        print(f"⚠  {n} screenings had no parseable 'Länge: X min.' — "
              f"using default {DEFAULT_DURATION_MIN} min (marked with * in the table)",
              file=sys.stderr)

    if not args.no_table:
        print_table(all_screenings)

    if args.schedule:
        by_film = {}
        for s in all_screenings:
            if s["start"] is not None:
                by_film.setdefault(s["film"], []).append(s)
        if not by_film:
            print("No screenings with parseable times — cannot schedule.", file=sys.stderr)
            return
        names = list(by_film.keys())

        print(f"\nScheduling {len(names)} films (buffer {BUFFER_MIN} min)...",
              file=sys.stderr)

        picked = cp_sat_schedule(by_film, workers=args.workers)
        if len(picked) == len(names):
            print(f"✓ Full schedule found for all {len(names)} films.", file=sys.stderr)
        else:
            print(f"✗ No full schedule possible. "
                  f"Optimal max-fit: {len(picked)} of {len(names)} films.", file=sys.stderr)

            # Interactive conflict resolution
            if args.interactive:
                if not HAVE_TUI:
                    print("⚠  --interactive requires 'simple-term-menu'. "
                          "Install with: pip install simple-term-menu", file=sys.stderr)
                else:
                    picked = interactive_resolve(by_film, picked, names, workers=args.workers)
                    print(f"\n✓ Final schedule: {len(picked)} films.", file=sys.stderr)

        print_schedule(picked, names)

        if args.ics:
            write_ics(picked, args.ics)
            print(f"  ICS calendar written to {args.ics} ({len(picked)} events)",
                  file=sys.stderr)
    elif args.ics:
        print("⚠  --ics ignored: requires --schedule to know which screenings to include",
              file=sys.stderr)

if __name__ == "__main__":
    main()
