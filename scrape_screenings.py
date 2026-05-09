#!/usr/bin/env python3
"""
DOK.fest München schedule planner.

Usage:
    docker run --rm -it -v "$PWD:/data" dokfest filme.txt
    docker run --rm -it -v "$PWD:/data" dokfest filme.txt --buffer 30

Reads URLs from the input file, scrapes screenings, builds a conflict-free
schedule (with interactive conflict resolution), and writes:
    filme.md  — markdown table + schedule
    filme.ics — calendar file
"""
import sys
import os
import re
import time
import argparse
import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from simple_term_menu import TerminalMenu
from ortools.sat.python import cp_model

BASE = "https://www.dokfest-muenchen.de"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}
DELAY = 0.5
DEFAULT_DURATION_MIN = 90
BUFFER_MIN = 15


# ───────────────────────── parsing ─────────────────────────

def parse_duration_from_h2(h2_text):
    m = re.search(r"Länge:\s*(\d+)\s*min", h2_text)
    return int(m.group(1)) if m else None

def parse_datetime(date_str, time_str):
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

    # Check for "#Nur im Kino" tag (German for "Only in cinemas")
    cinema_only = False
    for tag in soup.select('a[href*="films_tag"]'):
        if "nur im kino" in tag.get_text().lower():
            cinema_only = True
            break

    rows = []
    seen = set()
    for li in soup.select(".eventdate li"):
        ics = li.select_one('a[href^="/ics/view/"]')
        ev  = li.select_one('a[href^="events/view/"]')
        if not ics or not ev:
            continue
        ics_url = urljoin(BASE, ics["href"])
        if ics_url in seen:
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
            "cinema_only":    cinema_only,
        })
    return rows

def fetch(url):
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.text


# ───────────────────────── scheduling ─────────────────────────

def conflicts(a, b):
    if a["start"] is None or b["start"] is None:
        return False
    a_end = a["start"] + timedelta(minutes=a["duration"] + BUFFER_MIN)
    b_end = b["start"] + timedelta(minutes=b["duration"] + BUFFER_MIN)
    return a["start"] < b_end and b["start"] < a_end

def cp_sat_schedule(by_film):
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

    for idxs in by_idx.values():
        if idxs:
            m.Add(sum(x[i] for i in idxs) <= 1)

    for i in range(len(flat)):
        for j in range(i + 1, len(flat)):
            if conflicts(flat[i], flat[j]):
                m.Add(x[i] + x[j] <= 1)

    m.Maximize(sum(x))
    solver = cp_model.CpSolver()
    status = solver.Solve(m)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return []
    return [flat[i] for i in range(len(flat)) if solver.Value(x[i])]


def find_blocking_films(picked, by_film, excluded):
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


def interactive_resolve(by_film, initial_picked, names):
    picked = initial_picked
    excluded = set()

    while len(picked) < len(names) - len(excluded):
        blocking = find_blocking_films(picked, by_film, excluded)
        if not blocking:
            break

        unpicked_film = min(blocking.keys(), key=lambda f: len(blocking[f]))
        blockers = blocking[unpicked_film]

        blocking_films = {}
        for picked_scr, unpicked_scr in blockers:
            blocking_films.setdefault(picked_scr["film"], []).append((picked_scr, unpicked_scr))

        blocking_film = list(blocking_films.keys())[0]

        n_scheduled = len(picked)
        n_total = len(names) - len(excluded)

        # Check cinema_only status for both films
        unpicked_cinema = any(s.get("cinema_only") for s in by_film.get(unpicked_film, []))
        blocking_cinema = any(s.get("cinema_only") for s in by_film.get(blocking_film, []))

        unpicked_tag = " #NurImKino" if unpicked_cinema else ""
        blocking_tag = " #NurImKino" if blocking_cinema else ""

        print(f"\n{'─' * 60}", file=sys.stderr)
        print(f"  Schedule: {n_scheduled} of {n_total} films", file=sys.stderr)
        print(f"  \"{unpicked_film}\"{unpicked_tag} cannot be scheduled.", file=sys.stderr)
        print(f"  It conflicts with \"{blocking_film}\"{blocking_tag} (currently scheduled).", file=sys.stderr)
        print(f"{'─' * 60}\n", file=sys.stderr)

        options = [
            f"Keep \"{blocking_film}\"{blocking_tag} — skip \"{unpicked_film}\"",
            f"Keep \"{unpicked_film}\"{unpicked_tag} — remove \"{blocking_film}\"",
            "Accept current schedule",
        ]

        menu = TerminalMenu(
            options,
            title="  What would you like to do?",
            menu_cursor_style=("fg_cyan", "bold"),
            menu_highlight_style=("bg_gray", "fg_black"),
        )
        choice = menu.show()

        if choice is None or choice == 2:
            break
        elif choice == 0:
            excluded.add(unpicked_film)
            print(f"  → Skipping \"{unpicked_film}\"", file=sys.stderr)
        elif choice == 1:
            excluded.add(blocking_film)
            print(f"  → Removing \"{blocking_film}\", re-solving...", file=sys.stderr)
            filtered = {f: s for f, s in by_film.items() if f not in excluded}
            picked = cp_sat_schedule(filtered)

    return picked


# ───────────────────────── output ─────────────────────────

def md_row(cells):
    return "| " + " | ".join(str(c).replace("|", "\\|").replace("\n", " ") for c in cells) + " |"

def format_table(screenings):
    lines = []
    cols = ["Film", "Date", "Time", "Venue", "Duration", "ICS", "Comment"]
    lines.append(md_row(cols))
    lines.append("|" + "|".join(["---"] * len(cols)) + "|")
    for s in screenings:
        dur = f"{s['duration']} min" + ("" if s["duration_known"] else "*")
        lines.append(md_row([s["film"], s["date_str"], s["time_str"], s["venue"],
                             dur, s["ics"], s["comment"]]))
    return "\n".join(lines)

def format_schedule(picked, all_film_names):
    lines = ["\n## Personal schedule\n"]
    last_date = None
    for s in sorted(picked, key=lambda x: x["start"]):
        d = s["start"].date()
        if d != last_date:
            lines.append(f"\n### {s['start'].strftime('%a, %d %b %Y')}\n")
            last_date = d
        end = s["start"] + timedelta(minutes=s["duration"])
        line = (f"- **{s['start'].strftime('%H:%M')}–{end.strftime('%H:%M')}**  "
                f"_{s['venue']}_  —  {s['film']} ({s['duration']} min)")
        if s["comment"]:
            line += f"\n    - _{s['comment']}_"
        lines.append(line)
    scheduled = {s["film"] for s in picked}
    missing = [f for f in all_film_names if f not in scheduled]
    if missing:
        lines.append(f"\n### Not scheduled ({len(missing)})\n")
        for f in missing:
            lines.append(f"- {f}")
    return "\n".join(lines)


# ───────────────────────── ICS output ─────────────────────────

def extract_vevent(ics_text):
    """Extract VEVENT block from an ICS file."""
    start = ics_text.find("BEGIN:VEVENT")
    end = ics_text.find("END:VEVENT")
    if start == -1 or end == -1:
        return None
    return ics_text[start:end + len("END:VEVENT")]

def write_ics(picked, path):
    """Fetch official ICS files and merge them into one calendar."""
    vevents = []
    for s in sorted(picked, key=lambda x: x["start"]):
        try:
            ics_text = fetch(s["ics"])
            vevent = extract_vevent(ics_text)
            if vevent:
                vevents.append(vevent)
        except Exception as e:
            print(f"  ! ICS fetch error for {s['film']}: {e}", file=sys.stderr)

    content = "BEGIN:VCALENDAR\r\n"
    content += "VERSION:2.0\r\n"
    content += "PRODID:-//dokfest-planner//merged//EN\r\n"
    content += "CALSCALE:GREGORIAN\r\n"
    content += "METHOD:PUBLISH\r\n"
    for vevent in vevents:
        # Normalize line endings
        vevent = vevent.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\r\n")
        content += vevent + "\r\n"
    content += "END:VCALENDAR\r\n"

    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(content)


# ───────────────────────── main ─────────────────────────

def main():
    global BUFFER_MIN

    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input_file", help="text file with one film URL per line")
    ap.add_argument("--buffer", type=int, default=BUFFER_MIN,
                    help=f"minutes between screenings (default {BUFFER_MIN})")
    args = ap.parse_args()

    BUFFER_MIN = args.buffer

    # Derive output paths from input filename
    base = os.path.splitext(args.input_file)[0]
    md_path = base + ".md"
    ics_path = base + ".ics"

    # Read URLs from file
    with open(args.input_file) as f:
        urls = [line.strip() for line in f if line.strip()]

    if not urls:
        sys.exit("No URLs found in input file")

    # Scrape
    all_screenings = []
    for i, url in enumerate(urls, 1):
        print(f"[{i}/{len(urls)}] {url}", file=sys.stderr)
        try:
            all_screenings.extend(parse(fetch(url)))
        except Exception as e:
            print(f"  ! error: {e}", file=sys.stderr)
        if i < len(urls):
            time.sleep(DELAY)

    if any(not s["duration_known"] for s in all_screenings):
        n = sum(1 for s in all_screenings if not s["duration_known"])
        print(f"⚠  {n} screenings using default {DEFAULT_DURATION_MIN} min duration",
              file=sys.stderr)

    # Schedule
    by_film = {}
    for s in all_screenings:
        if s["start"] is not None:
            by_film.setdefault(s["film"], []).append(s)

    if not by_film:
        sys.exit("No screenings with parseable times")

    names = list(by_film.keys())
    print(f"\nScheduling {len(names)} films (buffer {BUFFER_MIN} min)...", file=sys.stderr)

    picked = cp_sat_schedule(by_film)

    if len(picked) == len(names):
        print(f"✓ Full schedule: all {len(names)} films.", file=sys.stderr)
    else:
        print(f"✗ Conflicts: {len(picked)} of {len(names)} films fit.", file=sys.stderr)
        picked = interactive_resolve(by_film, picked, names)
        print(f"\n✓ Final schedule: {len(picked)} films.", file=sys.stderr)

    # Write outputs
    md_content = format_table(all_screenings) + "\n" + format_schedule(picked, names)
    with open(md_path, "w") as f:
        f.write(md_content)
    print(f"  → {md_path}", file=sys.stderr)

    write_ics(picked, ics_path)
    print(f"  → {ics_path} ({len(picked)} events)", file=sys.stderr)


if __name__ == "__main__":
    main()
