"""
German public holidays calculation using Gauss Easter algorithm.
Supports all 16 Bundesländer.
"""
from datetime import date, timedelta

# Feiertage die nur in bestimmten Bundesländern gelten
STATE_HOLIDAYS = {
    "heilige_drei_koenige": {"BW", "BY", "ST"},
    "frauentag": {"BE", "MV"},
    "fronleichnam": {"BW", "BY", "HE", "NW", "RP", "SL"},
    "maria_himmelfahrt": {"BY", "SL"},
    "weltkindertag": {"TH"},
    "reformationstag": {"BB", "HB", "HH", "MV", "NI", "SN", "SH", "TH"},
    "allerheiligen": {"BW", "BY", "NW", "RP", "SL"},
    "buss_und_bettag": {"SN"},
}


def easter(year: int) -> date:
    """Gauss algorithm for Easter Sunday."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def get_holidays(year: int, state: str = "BY") -> dict[date, str]:
    """Return dict of {date: name} for all public holidays in the given year and state."""
    e = easter(year)
    holidays = {
        date(year, 1, 1): "Neujahr",
        e - timedelta(days=2): "Karfreitag",
        e: "Ostersonntag",
        e + timedelta(days=1): "Ostermontag",
        date(year, 5, 1): "Tag der Arbeit",
        e + timedelta(days=39): "Christi Himmelfahrt",
        e + timedelta(days=49): "Pfingstsonntag",
        e + timedelta(days=50): "Pfingstmontag",
        date(year, 10, 3): "Tag der Deutschen Einheit",
        date(year, 12, 25): "1. Weihnachtstag",
        date(year, 12, 26): "2. Weihnachtstag",
    }

    if state in STATE_HOLIDAYS.get("heilige_drei_koenige", set()):
        holidays[date(year, 1, 6)] = "Heilige Drei Könige"
    if state in STATE_HOLIDAYS.get("frauentag", set()):
        holidays[date(year, 3, 8)] = "Internationaler Frauentag"
    if state in STATE_HOLIDAYS.get("fronleichnam", set()):
        holidays[e + timedelta(days=60)] = "Fronleichnam"
    if state in STATE_HOLIDAYS.get("maria_himmelfahrt", set()):
        holidays[date(year, 8, 15)] = "Mariä Himmelfahrt"
    if state in STATE_HOLIDAYS.get("weltkindertag", set()):
        holidays[date(year, 9, 20)] = "Weltkindertag"
    if state in STATE_HOLIDAYS.get("reformationstag", set()):
        holidays[date(year, 10, 31)] = "Reformationstag"
    if state in STATE_HOLIDAYS.get("allerheiligen", set()):
        holidays[date(year, 11, 1)] = "Allerheiligen"
    if state in STATE_HOLIDAYS.get("buss_und_bettag", set()):
        # Wednesday before Nov 23
        nov23 = date(year, 11, 23)
        offset = (nov23.weekday() - 2) % 7
        holidays[nov23 - timedelta(days=offset)] = "Buß- und Bettag"

    return holidays


def is_holiday(d: date, state: str = "BY") -> str | None:
    """Return holiday name if date is a holiday, else None."""
    holidays = get_holidays(d.year, state)
    return holidays.get(d)


def is_weekend(d: date) -> bool:
    return d.weekday() >= 5
