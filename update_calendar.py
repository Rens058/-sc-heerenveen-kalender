from __future__ import annotations

import re
import sys
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

TEAM_KEYWORDS = ["heerenveen", "sc heerenveen"]
OUTPUT = Path("heerenveen.ics")
TZ = ZoneInfo("Europe/Amsterdam")

SEASONS = [
    ("2026-27", 2026),
    ("2025-26", 2025),
]

BASE_URL = "https://raw.githubusercontent.com/openfootball/europe/master/netherlands/{season}_nl1.txt"

MONTHS = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4,
    "May": 5, "Jun": 6, "Jul": 7, "Aug": 8,
    "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}


@dataclass
class Match:
    start: datetime
    home: str
    away: str

    @property
    def is_home(self) -> bool:
        return "heerenveen" in self.home.lower()

    @property
    def title(self) -> str:
        label = "Thuis" if self.is_home else "Uit"
        return f"{self.home} - {self.away} ({label})"


def fetch_text(url: str) -> str | None:
    try:
        with urllib.request.urlopen(url, timeout=20) as response:
            if response.status == 200:
                return response.read().decode("utf-8")
    except Exception as exc:
        print(f"Bron niet beschikbaar: {url} ({exc})")
    return None


def parse_date_line(line: str, season_year: int) -> datetime | None:
    match = re.match(r"^(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+([A-Z][a-z]{2})\s+(\d{1,2})$", line.strip())
    if not match:
        return None

    _, month_name, day = match.groups()
    month = MONTHS[month_name]
    year = season_year if month >= 7 else season_year + 1

    return datetime(year, month, int(day), tzinfo=TZ)


def parse_match_line(line: str, current_date: datetime | None) -> Match | None:
    if current_date is None:
        return None

    line = line.strip()
    match = re.match(r"^(\d{1,2}:\d{2})\s+(.+?)\s+v\s+(.+?)(?:\s+\d.*)?$", line)
    if not match:
        return None

    time_part, home, away = match.groups()

    if "heerenveen" not in home.lower() and "heerenveen" not in away.lower():
        return None

    hour, minute = map(int, time_part.split(":"))
    start = current_date.replace(hour=hour, minute=minute)

    return Match(start=start, home=home.strip(), away=away.strip())


def escape_ics(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace(",", "\\,")
        .replace(";", "\\;")
        .replace("\n", "\\n")
    )


def ics_time(dt: datetime) -> str:
    return dt.strftime("%Y%m%dT%H%M%S")


def make_ics(matches: list[Match], season: str) -> str:
    now = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Abe Agenda//SC Heerenveen//NL",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Abe Agenda - SC Heerenveen",
        "X-WR-TIMEZONE:Europe/Amsterdam",
    ]

    for m in matches:
        end = m.start + timedelta(hours=2)
        uid_base = f"{m.start:%Y%m%d%H%M}-{m.home}-{m.away}".lower()
        uid_base = re.sub(r"[^a-z0-9]+", "-", uid_base).strip("-")

        lines.extend([
            "BEGIN:VEVENT",
            f"UID:{uid_base}@abe-agenda",
            f"DTSTAMP:{now}",
            f"DTSTART;TZID=Europe/Amsterdam:{ics_time(m.start)}",
            f"DTEND;TZID=Europe/Amsterdam:{ics_time(end)}",
            f"SUMMARY:{escape_ics(m.title)}",
            f"DESCRIPTION:{escape_ics(f'Abe Agenda - SC Heerenveen kalender. Bron: OpenFootball. Seizoen: {season}.')}",
            "END:VEVENT",
        ])

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def parse_season(text: str, season_year: int) -> list[Match]:
    matches: list[Match] = []
    current_date: datetime | None = None

    for line in text.splitlines():
        date = parse_date_line(line, season_year)
        if date:
            current_date = date
            continue

        match = parse_match_line(line, current_date)
        if match:
            matches.append(match)

    return sorted(matches, key=lambda m: m.start)


def main() -> int:
    for season, season_year in SEASONS:
        url = BASE_URL.format(season=season)
        print(f"Controleer {season}: {url}")

        text = fetch_text(url)
        if not text:
            continue

        matches = parse_season(text, season_year)

        if matches:
            OUTPUT.write_text(make_ics(matches, season), encoding="utf-8")
            print(f"{OUTPUT} bijgewerkt met {len(matches)} wedstrijden voor {season}.")
            return 0

        print(f"Geen SC Heerenveen-wedstrijden gevonden voor {season}.")

    print("Geen bruikbare wedstrijden gevonden. Bestaande heerenveen.ics blijft behouden.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
