from __future__ import annotations

import re
import sys
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

TEAM = "SC Heerenveen"
OUTPUT = Path("heerenveen.ics")
TZ = ZoneInfo("Europe/Amsterdam")

SEASONS = [
    ("2026-27", 2026),
    ("2025-26", 2025),
]

BASE_URL = "https://raw.githubusercontent.com/openfootball/europe/master/netherlands/{season}_nl1.txt"


@dataclass
class Match:
    start: datetime
    home: str
    away: str

    @property
    def is_home(self) -> bool:
        return TEAM.lower() in self.home.lower()

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
        print(f"Kon bron niet ophalen: {url} ({exc})")
    return None


def parse_date_header(line: str, season_year: int) -> datetime | None:
    match = re.match(r"\[(?:\w+\s+)?([A-Za-z]{3})/(\d{1,2})\]", line.strip())
    if not match:
        return None

    month_name, day = match.groups()
    month = datetime.strptime(month_name, "%b").month
    year = season_year if month >= 7 else season_year + 1
    return datetime(year, month, int(day), tzinfo=TZ)


def parse_match_line(line: str, current_date: datetime | None) -> Match | None:
    if not current_date:
        return None

    parts = re.split(r"\s{2,}", line.strip())
    if len(parts) < 3:
        return None

    time_part = parts[0].replace(".", ":")
    if not re.match(r"^\d{1,2}:\d{2}$", time_part):
        return None

    home = parts[1].strip()
    away = parts[-1].strip()

    if "heerenveen" not in home.lower() and "heerenveen" not in away.lower():
        return None

    hour, minute = map(int, time_part.split(":"))
    start = current_date.replace(hour=hour, minute=minute)

    return Match(start=start, home=home, away=away)


def ics_datetime(dt: datetime) -> str:
    return dt.strftime("%Y%m%dT%H%M%S")


def escape_ics(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace(",", "\\,")
        .replace(";", "\\;")
        .replace("\n", "\\n")
    )


def make_ics(matches: list[Match]) -> str:
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

    for match in matches:
        end = match.start + timedelta(hours=2)
        uid = f"{match.start.strftime('%Y%m%d%H%M')}-{match.home}-{match.away}@abe-agenda"
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{escape_ics(uid)}",
                f"DTSTAMP:{now}",
                f"DTSTART;TZID=Europe/Amsterdam:{ics_datetime(match.start)}",
                f"DTEND;TZID=Europe/Amsterdam:{ics_datetime(end)}",
                f"SUMMARY:{escape_ics(match.title)}",
                f"DESCRIPTION:{escape_ics('Abe Agenda - automatisch gegenereerde SC Heerenveen-kalender.')}",
                "END:VEVENT",
            ]
        )

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def main() -> int:
    all_matches: list[Match] = []

    for season, season_year in SEASONS:
        url = BASE_URL.format(season=season)
        print(f"Controleer seizoen {season}: {url}")
        text = fetch_text(url)

        if not text:
            continue

        current_date = None
        matches: list[Match] = []

        for line in text.splitlines():
            date_header = parse_date_header(line, season_year)
            if date_header:
                current_date = date_header
                continue

            match = parse_match_line(line, current_date)
            if match:
                matches.append(match)

        if matches:
            print(f"{len(matches)} wedstrijden gevonden voor {season}.")
            all_matches = matches
            break

    if not all_matches:
        print("Geen SC Heerenveen-wedstrijden gevonden. Bestaande heerenveen.ics blijft behouden.")
        return 0

    all_matches.sort(key=lambda m: m.start)
    OUTPUT.write_text(make_ics(all_matches), encoding="utf-8")
    print(f"{OUTPUT} bijgewerkt met {len(all_matches)} wedstrijden.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
