"""
ArbZG (Arbeitszeitgesetz) compliance checking and correction.

§3: Max 10h/Tag, Durchschnitt ≤8h über 24 Wochen
§4: Pause 30min >6h, 45min >9h
§5: Ruhezeit ≥11h zwischen Arbeitstagen
§9: Keine Sonn-/Feiertagsarbeit
"""
from datetime import date, datetime, timedelta
from dataclasses import dataclass, field

from holidays import is_holiday, is_weekend


@dataclass
class DayInfo:
    date: date
    actual_hours: float
    entries: list = field(default_factory=list)  # list of TimeEntry
    is_weekend: bool = False
    holiday: str | None = None
    violations: list[str] = field(default_factory=list)


@dataclass
class CorrectedDay:
    date: date
    corrected_hours: float
    start_time: str  # "HH:MM"
    end_time: str    # "HH:MM"
    pause_minutes: int
    day_type: str    # "Arbeit", "Wochenende", "Feiertag", "Urlaub", "Krank", "Gleittag"
    original_hours: float = 0.0


def check_violations(days: list[DayInfo], state: str = "BY") -> list[DayInfo]:
    """Check all ArbZG violations for a list of days."""
    for i, day in enumerate(days):
        day.is_weekend = is_weekend(day.date)
        day.holiday = is_holiday(day.date, state)
        day.violations = []

        if day.actual_hours == 0:
            continue

        # §9: Sunday/holiday work
        if day.date.weekday() == 6:  # Sunday
            day.violations.append("§9 Sonntag")
        if day.holiday:
            day.violations.append(f"§9 Feiertag ({day.holiday})")

        # §3: Max 10h/day
        if day.actual_hours > 10:
            day.violations.append(f"§3 >10h ({day.actual_hours:.1f}h)")

        # §4: Break requirements (only check if multiple entries allow gap measurement)
        if day.actual_hours > 6 and len(day.entries) >= 2:
            required_break = 45 if day.actual_hours > 9 else 30
            actual_break = _calculate_break_minutes(day.entries)
            if actual_break < required_break:
                day.violations.append(
                    f"§4 Pause ({actual_break}min < {required_break}min)"
                )

        # §5: Rest period ≥11h between days
        if i > 0 and days[i - 1].entries and day.entries:
            prev_end = max(e.end for e in days[i - 1].entries)
            curr_start = min(e.start for e in day.entries)
            rest_hours = (curr_start - prev_end).total_seconds() / 3600
            if rest_hours < 11:
                day.violations.append(f"§5 Ruhezeit ({rest_hours:.1f}h < 11h)")

    # §3: 24-week average ≤8h (check rolling windows)
    _check_24week_average(days)

    return days


def _calculate_break_minutes(entries: list) -> int:
    """Calculate total break time from gaps between entries."""
    if len(entries) < 2:
        return 0
    sorted_entries = sorted(entries, key=lambda e: e.start)
    total_break = 0
    for i in range(1, len(sorted_entries)):
        gap = (sorted_entries[i].start - sorted_entries[i - 1].end).total_seconds() / 60
        if gap > 0:
            total_break += gap
    return int(total_break)


def _check_24week_average(days: list[DayInfo]):
    """Check if 24-week rolling average exceeds 8h/day (working days only)."""
    working_days = [d for d in days if not d.is_weekend and not d.holiday and d.actual_hours > 0]
    window_size = 24 * 5  # ~24 weeks * 5 working days
    if len(working_days) < window_size:
        return
    for i in range(len(working_days) - window_size + 1):
        window = working_days[i:i + window_size]
        avg = sum(d.actual_hours for d in window) / len(window)
        if avg > 8:
            # Mark the last day in the window
            last = window[-1]
            violation = f"§3 Ø>8h ({avg:.1f}h/24W)"
            if violation not in last.violations:
                last.violations.append(violation)


def correct_for_office(days: list[DayInfo], state: str = "BY", hours_per_day: float = 7.8) -> list[CorrectedDay]:
    """
    Produce ArbZG-compliant corrected version.
    - Weekend/holiday hours → carry over to next working day
    - Cap at 10h/day, excess → carry over
    - Generate plausible start/end/pause times
    - Paid absence (Urlaub/Krank/Gleittag) → Ist = Soll = hours_per_day
    """
    corrected = []
    carry_over = 0.0

    for day in days:
        holiday = is_holiday(day.date, state)
        weekend = is_weekend(day.date)

        # Determine day type from project names
        day_type = _detect_day_type(day)

        if day_type in ("Urlaub", "Krank"):
            # Paid absence: Ist = Soll (no overtime change)
            start_time, end_time, pause_min = _generate_times(hours_per_day)
            corrected.append(CorrectedDay(
                date=day.date,
                corrected_hours=hours_per_day,
                start_time=start_time,
                end_time=end_time,
                pause_minutes=pause_min,
                day_type=day_type,
                original_hours=day.actual_hours,
            ))
            continue

        if day_type == "Gleittag":
            # Overtime reduction: Ist = 0, Soll remains hours_per_day
            corrected.append(CorrectedDay(
                date=day.date,
                corrected_hours=0,
                start_time="",
                end_time="",
                pause_minutes=0,
                day_type=day_type,
                original_hours=day.actual_hours,
            ))
            continue

        if weekend or holiday:
            carry_over += day.actual_hours
            dtype = "Feiertag" if holiday else ("Samstag" if day.date.weekday() == 5 else "Sonntag")
            corrected.append(CorrectedDay(
                date=day.date,
                corrected_hours=0,
                start_time="",
                end_time="",
                pause_minutes=0,
                day_type=dtype,
                original_hours=day.actual_hours,
            ))
            continue

        # Working day: add carry-over
        total = day.actual_hours + carry_over
        if total > 10:
            carry_over = total - 10
            effective = 10.0
        else:
            carry_over = 0.0
            effective = total

        if effective <= 0:
            corrected.append(CorrectedDay(
                date=day.date,
                corrected_hours=0,
                start_time="",
                end_time="",
                pause_minutes=0,
                day_type="Arbeit",
                original_hours=day.actual_hours,
            ))
            continue

        # Generate plausible times
        start_time, end_time, pause_min = _generate_times(effective)

        corrected.append(CorrectedDay(
            date=day.date,
            corrected_hours=round(effective, 2),
            start_time=start_time,
            end_time=end_time,
            pause_minutes=pause_min,
            day_type="Arbeit",
            original_hours=day.actual_hours,
        ))

    # If there's remaining carry-over, distribute to last working days
    if carry_over > 0:
        _distribute_remaining_carry(corrected, carry_over)

    return corrected


def _detect_day_type(day: DayInfo) -> str:
    """Detect special day types from project names."""
    if not day.entries:
        return "Arbeit"
    project_names = {e.project_name.lower() for e in day.entries}
    for name in project_names:
        if "urlaub" in name:
            return "Urlaub"
        if "krank" in name:
            return "Krank"
        if "gleittag" in name or "gleitzeit" in name:
            return "Gleittag"
    return "Arbeit"


def _generate_times(hours: float) -> tuple[str, str, int]:
    """Generate plausible start/end/pause for given hours."""
    start_hour = 8
    start_min = 0

    if hours > 9:
        pause_min = 45
    elif hours > 6:
        pause_min = 30
    else:
        pause_min = 0

    total_minutes = int(hours * 60) + pause_min
    end_hour = start_hour + total_minutes // 60
    end_min = start_min + total_minutes % 60
    if end_min >= 60:
        end_hour += 1
        end_min -= 60

    return (
        f"{start_hour:02d}:{start_min:02d}",
        f"{end_hour:02d}:{end_min:02d}",
        pause_min,
    )


def _distribute_remaining_carry(corrected: list[CorrectedDay], carry: float):
    """Add remaining carry-over hours to last working days (up to 10h cap)."""
    for day in reversed(corrected):
        if carry <= 0:
            break
        if day.day_type == "Arbeit" and day.corrected_hours > 0 and day.corrected_hours < 10:
            space = 10 - day.corrected_hours
            add = min(space, carry)
            day.corrected_hours = round(day.corrected_hours + add, 2)
            carry -= add
            day.start_time, day.end_time, day.pause_minutes = _generate_times(day.corrected_hours)
