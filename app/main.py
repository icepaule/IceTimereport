#!/usr/bin/env python3
"""
Overtime Report Generator - CLI Entry Point

Usage:
    python main.py generate [--year YYYY]
    python main.py send-email [--year YYYY] [--month MM] [--test]
    python main.py check [--year YYYY]
"""
import argparse
import os
import sys
from datetime import date, timedelta
from collections import defaultdict

import db
import holidays as hol
from holidays import is_weekend, is_holiday
import azg
import excel_real
import excel_office
import mailer


def _detect_day_type_from_entries(day_info: azg.DayInfo) -> str:
    """Detect Urlaub/Krank/Gleittag from Solidtime project names."""
    if not day_info.entries:
        return "Arbeit"
    projects = {e.project_name.lower() for e in day_info.entries}
    for p in projects:
        if "urlaub" in p:
            return "Urlaub"
        if "krank" in p:
            return "Krank"
        if "gleittag" in p or "gleitzeit" in p:
            return "Gleittag"
    return "Arbeit"


def get_config():
    return {
        "employee_name": os.environ.get("EMPLOYEE_NAME", "Mitarbeiter"),
        "employee_role": os.environ.get("EMPLOYEE_ROLE", ""),
        "hours_per_week": float(os.environ.get("HOURS_PER_WEEK", "39")),
        "vacation_days": int(os.environ.get("VACATION_DAYS", "30")),
        "start_date": os.environ.get("START_DATE", "2024-01-01"),
        "state": os.environ.get("STATE", "BY"),
        "output_dir_real": os.environ.get("OUTPUT_DIR_REAL", "/output/real"),
        "output_dir_office": os.environ.get("OUTPUT_DIR_OFFICE", "/output/office"),
    }


def build_day_infos(year: int, config: dict) -> list[azg.DayInfo]:
    """Fetch entries and build DayInfo list for entire year."""
    start = date(year, 1, 1)
    end = min(date(year, 12, 31), date.today())

    entries = db.fetch_entries(start, end)

    # Group entries by date
    by_date: dict[date, list] = defaultdict(list)
    for e in entries:
        by_date[e.start.date()].append(e)

    # Build DayInfo for every calendar day
    days = []
    current = start
    while current <= end:
        day_entries = by_date.get(current, [])
        actual_hours = sum(e.hours for e in day_entries)
        day = azg.DayInfo(
            date=current,
            actual_hours=round(actual_hours, 4),
            entries=day_entries,
        )
        days.append(day)
        current += timedelta(days=1)

    return days


def _calc_year_overtime(days: list[azg.DayInfo], state: str, hours_per_day: float) -> float:
    """Calculate overtime for a list of DayInfos (single year)."""
    total_actual = 0.0
    total_target = 0.0
    for d in days:
        if is_weekend(d.date) or is_holiday(d.date, state):
            total_actual += d.actual_hours
            continue
        day_type = _detect_day_type_from_entries(d)
        if day_type in ("Urlaub", "Krank"):
            total_actual += hours_per_day
            total_target += hours_per_day
        elif day_type == "Gleittag":
            total_target += hours_per_day
        elif d.actual_hours > 0:
            total_actual += d.actual_hours
            total_target += hours_per_day
        else:
            total_target += hours_per_day
    return total_actual - total_target


def _calc_vacation_carryover(year: int, config: dict) -> int:
    """Count vacation days at the start of `year` that belong to previous year's vacation period.

    If there is a contiguous block of Urlaub days at the start of the year that connects
    back to Urlaub days in December of the previous year, those January days count
    against the previous year's vacation allowance.
    """
    start_date = date.fromisoformat(config["start_date"])
    if year <= start_date.year:
        return 0  # No carryover for the first year

    # Check if there are Urlaub entries in December of previous year
    prev_dec_entries = db.fetch_entries(date(year - 1, 12, 1), date(year - 1, 12, 31))
    dec_dates_with_urlaub: set[date] = set()
    by_date: dict[date, list] = defaultdict(list)
    for e in prev_dec_entries:
        by_date[e.start.date()].append(e)
    for d, entries in by_date.items():
        projects = {e.project_name.lower() for e in entries}
        if any("urlaub" in p for p in projects):
            dec_dates_with_urlaub.add(d)

    if not dec_dates_with_urlaub:
        return 0

    # Check if Dec 31 has Urlaub (or last working day before it)
    dec31 = date(year - 1, 12, 31)
    # Walk backwards from Dec 31 to find the last non-weekend/non-holiday day
    check = dec31
    while check >= date(year - 1, 12, 20):
        if not is_weekend(check) and not is_holiday(check, config["state"]):
            break
        check -= timedelta(days=1)

    if check not in dec_dates_with_urlaub:
        return 0  # Previous year doesn't end with Urlaub

    # Count contiguous Urlaub days at start of current year
    jan_entries = db.fetch_entries(date(year, 1, 1), date(year, 1, 31))
    jan_by_date: dict[date, list] = defaultdict(list)
    for e in jan_entries:
        jan_by_date[e.start.date()].append(e)

    carryover = 0
    current = date(year, 1, 1)
    while current.month == 1:
        if is_weekend(current) or is_holiday(current, config["state"]):
            current += timedelta(days=1)
            continue
        entries = jan_by_date.get(current, [])
        if entries:
            projects = {e.project_name.lower() for e in entries}
            if any("urlaub" in p for p in projects):
                carryover += 1
                current += timedelta(days=1)
                continue
        break  # First non-Urlaub weekday ends the contiguous block

    return carryover


def _generate_year(year: int, config: dict, prior_overtime: float):
    """Generate both reports for a single year with carry-over from prior years."""
    state = config["state"]
    hours_per_day = config["hours_per_week"] / 5

    print(f"\nGenerating reports for {year} (State: {state})...")
    if prior_overtime != 0:
        print(f"  Carry-over from prior years: {prior_overtime:+.2f}h")

    # Calculate vacation carryover from previous year
    vacation_carryover = _calc_vacation_carryover(year, config)
    if vacation_carryover:
        print(f"  Vacation carryover from previous year: {vacation_carryover} days")

    days = build_day_infos(year, config)

    # Check ArbZG violations
    print("  Checking ArbZG compliance...")
    azg.check_violations(days, state)

    violation_count = sum(1 for d in days if d.violations)
    total_violations = sum(len(d.violations) for d in days)
    print(f"  {violation_count} days with violations ({total_violations} total violations)")

    # Generate real report
    print("  Generating real report...")
    real_path = excel_real.generate(
        year, days,
        output_dir=config["output_dir_real"],
        employee_name=config["employee_name"],
        employee_role=config["employee_role"],
        state=state,
        prior_overtime=prior_overtime,
        vacation_carryover=vacation_carryover,
    )
    print(f"  -> {real_path}")

    # Correct for office version
    print("  Applying ArbZG corrections for office version...")
    corrected = azg.correct_for_office(days, state, hours_per_day=hours_per_day)
    # Compare working hours (exclude paid absence and overtime reduction days)
    paid_absence = {"Urlaub", "Krank"}
    non_work = {"Urlaub", "Krank", "Gleittag", "Samstag", "Sonntag", "Feiertag"}
    total_work_orig = sum(
        d.actual_hours for d, c in zip(days, corrected)
        if d.actual_hours > 0 and c.day_type not in non_work
    )
    total_corr_work = sum(
        d.corrected_hours for d in corrected
        if d.day_type not in non_work
    )
    paid_days = sum(1 for d in corrected if d.day_type in paid_absence)
    gleittage = sum(1 for d in corrected if d.day_type == "Gleittag")
    print(f"  Working hours: {total_work_orig:.1f}h -> Corrected: {total_corr_work:.1f}h (delta: {total_corr_work - total_work_orig:.1f}h)")
    if paid_days:
        print(f"  Paid absence (Urlaub/Krank): {paid_days} days ({paid_days * hours_per_day:.1f}h, Ist=Soll)")
    if gleittage:
        print(f"  Overtime reduction (Gleittag): {gleittage} days (-{gleittage * hours_per_day:.1f}h)")

    # Generate office report
    print("  Generating office report...")
    office_path = excel_office.generate(
        year, corrected,
        output_dir=config["output_dir_office"],
        employee_name=config["employee_name"],
        employee_role=config["employee_role"],
        state=state,
        prior_overtime=prior_overtime,
        vacation_carryover=vacation_carryover,
    )
    print(f"  -> {office_path}")

    # Return this year's overtime for carry-over
    year_overtime = _calc_year_overtime(days, state, hours_per_day)
    print(f"  Year overtime: {year_overtime:+.2f}h | Cumulative: {prior_overtime + year_overtime:+.2f}h")
    return year_overtime


def cmd_generate(args):
    """Generate both Excel reports for all years since START_DATE."""
    config = get_config()
    state = config["state"]
    hours_per_day = config["hours_per_week"] / 5
    start_date = date.fromisoformat(config["start_date"])
    current_year = date.today().year

    if args.year:
        # Single year requested: calculate prior overtime from all years before it
        prior_overtime = 0.0
        for yr in range(start_date.year, args.year):
            yr_days = build_day_infos(yr, config)
            azg.check_violations(yr_days, state)
            prior_overtime += _calc_year_overtime(yr_days, state, hours_per_day)
        _generate_year(args.year, config, prior_overtime)
    else:
        # Generate all years from START_DATE with cumulative carry-over
        prior_overtime = 0.0
        for yr in range(start_date.year, current_year + 1):
            year_overtime = _generate_year(yr, config, prior_overtime)
            prior_overtime += year_overtime

    print("\nDone.")


def cmd_send_email(args):
    """Send monthly report via email."""
    config = get_config()
    year = args.year or date.today().year
    month = args.month or (date.today().month - 1 or 12)
    if month == 12 and not args.year:
        year -= 1
    state = config["state"]

    print(f"Preparing email for {month:02d}/{year}...")

    hours_per_day = config["hours_per_week"] / 5
    start_date = date.fromisoformat(config["start_date"])
    absence_types = ("Samstag", "Sonntag", "Feiertag")

    # Calculate TOTAL overtime since START_DATE across all years
    # - Urlaub/Krank: Ist = Soll = hours_per_day (paid absence, overtime neutral)
    # - Gleittag/empty weekday: Ist = 0, Soll = hours_per_day (overtime reduction)
    # - Weekend/holiday work: all hours count as overtime (Soll = 0)
    total_actual = 0.0
    total_target = 0.0
    total_vacation_used = 0
    current_year = start_date.year
    while current_year <= year:
        y_days = build_day_infos(current_year, config)
        azg.check_violations(y_days, state)

        for d in y_days:
            in_scope = (current_year < year) or (current_year == year and d.date.month <= month)
            if not in_scope:
                continue
            if is_weekend(d.date) or is_holiday(d.date, state):
                # Weekend/holiday work counts as overtime (all hours, 0 target)
                total_actual += d.actual_hours
                continue

            day_type = _detect_day_type_from_entries(d)
            if day_type == "Urlaub":
                total_actual += hours_per_day
                total_target += hours_per_day
                total_vacation_used += 1
            elif day_type == "Krank":
                total_actual += hours_per_day
                total_target += hours_per_day
            elif day_type == "Gleittag":
                # Overtime reduction: Soll counts, Ist = 0
                total_target += hours_per_day
            elif d.actual_hours > 0:
                # Working day with entries
                total_actual += d.actual_hours
                total_target += hours_per_day
            else:
                # Empty weekday (Brückentag / Überstundenabbau): Soll counts, Ist = 0
                total_target += hours_per_day

        current_year += 1
    total_overtime = total_actual - total_target

    # Current year data for monthly stats
    days = build_day_infos(year, config)
    azg.check_violations(days, state)
    corrected = azg.correct_for_office(days, state, hours_per_day=hours_per_day)

    non_work_types = ("Samstag", "Sonntag", "Feiertag")
    month_days_corr = [d for d in corrected if d.date.month == month]
    month_actual = sum(d.corrected_hours for d in month_days_corr)
    month_target = sum(
        hours_per_day
        for d in month_days_corr
        if d.day_type not in non_work_types
    )

    # Vacation: count current year only, subtract carryover from previous year
    yearly_vacation = sum(1 for d in corrected if d.date.month <= month and d.day_type == "Urlaub")
    vacation_carryover = _calc_vacation_carryover(year, config)
    effective_vacation = yearly_vacation - vacation_carryover

    summary = {
        "actual": month_actual,
        "target": month_target,
        "overtime_total": total_overtime,
        "vacation_remaining": config["vacation_days"] - effective_vacation,
    }

    office_file = os.path.join(
        config["output_dir_office"],
        f"Arbeitszeitnachweis_{year}.xlsx",
    )

    if not os.path.exists(office_file):
        print(f"Office report not found at {office_file}, generating first...")
        office_path = excel_office.generate(
            year, corrected,
            output_dir=config["output_dir_office"],
            employee_name=config["employee_name"],
            employee_role=config["employee_role"],
            state=state,
        )
    else:
        office_path = office_file

    success = mailer.send_monthly_report(
        year, month, office_path, summary, test=args.test,
    )
    if success:
        print("Email sent successfully.")
    else:
        print("Email sending failed.", file=sys.stderr)
        sys.exit(1)


def cmd_check(args):
    """Check ArbZG compliance and print summary."""
    config = get_config()
    year = args.year or date.today().year
    state = config["state"]

    days = build_day_infos(year, config)
    azg.check_violations(days, state)

    print(f"\nArbZG Check for {year} ({config['employee_name']}):")
    print("=" * 60)

    violation_days = [d for d in days if d.violations]
    if not violation_days:
        print("No violations found.")
        return

    for d in violation_days:
        v_str = ", ".join(d.violations)
        print(f"  {d.date.strftime('%d.%m.%Y')} ({d.actual_hours:.1f}h): {v_str}")

    # Summary by type
    print(f"\nSummary ({len(violation_days)} days with violations):")
    by_type: dict[str, int] = {}
    for d in violation_days:
        for v in d.violations:
            key = v.split("(")[0].strip()
            by_type[key] = by_type.get(key, 0) + 1
    for vtype, count in sorted(by_type.items()):
        print(f"  {vtype}: {count}x")


def main():
    parser = argparse.ArgumentParser(
        description="ArbZG-compliant Overtime Report Generator for Solidtime",
    )
    sub = parser.add_subparsers(dest="command", help="Command")

    p_gen = sub.add_parser("generate", help="Generate Excel reports")
    p_gen.add_argument("--year", type=int, help="Year (default: current)")

    p_email = sub.add_parser("send-email", help="Send monthly email report")
    p_email.add_argument("--year", type=int, help="Year (default: current)")
    p_email.add_argument("--month", type=int, help="Month (default: previous)")
    p_email.add_argument("--test", action="store_true", help="Send test email to self")

    p_check = sub.add_parser("check", help="Check ArbZG compliance")
    p_check.add_argument("--year", type=int, help="Year (default: current)")

    args = parser.parse_args()

    if args.command == "generate":
        cmd_generate(args)
    elif args.command == "send-email":
        cmd_send_email(args)
    elif args.command == "check":
        cmd_check(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
