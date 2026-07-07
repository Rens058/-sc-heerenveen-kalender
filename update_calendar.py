from __future__ import annotations
import re, html, hashlib
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import requests
from bs4 import BeautifulSoup

URL = "https://www.transfermarkt.com/sc-heerenveen/spielplan/verein/306"
TZ = ZoneInfo("Europe/Amsterdam")
TEAM = "SC Heerenveen"
OUT = "heerenveen.ics"

HEADERS = {"User-Agent": "Mozilla/5.0 (calendar updater; contact: GitHub Actions)"}

STADIUMS = {
    "H": "Abe Lenstra Stadion, Heerenveen",
}

def esc(s: str) -> str:
    return s.replace('\\','\\\\').replace(';','\\;').replace(',','\\,').replace('\n','\\n')

def uid(title: str, start: datetime) -> str:
    return hashlib.sha1(f"{title}-{start.isoformat()}".encode()).hexdigest()[:16] + "@sc-heerenveen-kalender"

def parse_date_time(date_s: str, time_s: str) -> datetime | None:
    # Examples: Sun 09/08/2026 and 4:45 PM, or 'Sun Aug 9, 2026'
    ds = re.sub(r"^[A-Za-z]{2,3}\s+", "", date_s.strip())
    for fmt in ["%d/%m/%Y", "%b %d, %Y", "%d.%m.%Y"]:
        try:
            d = datetime.strptime(ds, fmt).date()
            break
        except ValueError:
            d = None
    if d is None:
        return None
    ts = time_s.strip().replace("h", ":")
    for fmt in ["%I:%M %p", "%H:%M"]:
        try:
            t = datetime.strptime(ts, fmt).time()
            return datetime.combine(d, t, TZ)
        except ValueError:
            pass
    return datetime.combine(d, datetime.min.time(), TZ)

def scrape() -> list[dict]:
    r = requests.get(URL, headers=HEADERS, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")
    rows = soup.select("table.items tbody tr")
    events = []
    for tr in rows:
        txt = " ".join(tr.get_text(" ", strip=True).split())
        if not txt or ":" not in txt:
            continue
        # Transfermarkt table layout varies; use text pattern and links as fallback.
        date_m = re.search(r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+\d{2}/\d{2}/\d{4}", txt)
        time_m = re.search(r"\b\d{1,2}:\d{2}\s*(?:AM|PM)?\b", txt)
        if not date_m or not time_m:
            continue
        start = parse_date_time(date_m.group(0), time_m.group(0))
        if not start:
            continue
        venue = "H" if re.search(r"\bH\b", txt) else ("A" if re.search(r"\bA\b", txt) else "")
        links = [a.get_text(" ", strip=True) for a in tr.select("a") if a.get_text(strip=True)]
        opponent = "Tegenstander"
        for name in reversed(links):
            if TEAM.lower() not in name.lower() and len(name) > 2 and not name.isdigit():
                opponent = name
                break
        if venue == "H":
            title = f"{TEAM} - {opponent} (Thuis)"
            location = STADIUMS["H"]
        else:
            title = f"{opponent} - {TEAM} (Uit)"
            location = ""
        events.append({"title": title, "start": start, "end": start + timedelta(hours=2), "location": location, "source": URL})
    return events

def write_ics(events: list[dict]) -> None:
    now = datetime.now(ZoneInfo("UTC")).strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "CALSCALE:GREGORIAN", "METHOD:PUBLISH", "PRODID:-//Rens058//SC Heerenveen kalender//NL", "X-WR-CALNAME:SC Heerenveen", "X-WR-TIMEZONE:Europe/Amsterdam"]
    for e in events:
        s = e["start"].strftime("%Y%m%dT%H%M%S")
        en = e["end"].strftime("%Y%m%dT%H%M%S")
        lines += ["BEGIN:VEVENT", f"UID:{uid(e['title'], e['start'])}", f"DTSTAMP:{now}", f"SUMMARY:{esc(e['title'])}", f"DTSTART;TZID=Europe/Amsterdam:{s}", f"DTEND;TZID=Europe/Amsterdam:{en}"]
        if e.get("location"):
            lines.append(f"LOCATION:{esc(e['location'])}")
        lines.append(f"DESCRIPTION:{esc('Automatisch bijgewerkt via ' + e['source'])}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")

if __name__ == "__main__":
    try:
        events = scrape()
        if len(events) < 5:
            raise RuntimeError(f"Te weinig wedstrijden gevonden: {len(events)}")
        write_ics(events)
        print(f"Geschreven: {len(events)} wedstrijden")
    except Exception as exc:
        print(f"Update mislukt: {exc}")
        print("Bestaande heerenveen.ics blijft behouden.")
