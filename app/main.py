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


def cmd_generate(args):
    """Generate both Excel reports."""
    config = get_config()
    year = args.year or date.today().year
    state = config["state"]

    print(f"Generating reports for {year} (State: {state})...")

    days = build_day_infos(year, config)

    # Check ArbZG violations
    print("Checking ArbZG compliance...")
    azg.check_violations(days, state)

    violation_count = sum(1 for d in days if d.violations)
    total_violations = sum(len(d.violations) for d in days)
    print(f"  {violation_count} days with violations ({total_violations} total violations)")

    # Generate real report
    print("Generating real report...")
    real_path = excel_real.generate(
        year, days,
        output_dir=config["output_dir_real"],
        employee_name=config["employee_name"],
        employee_role=config["employee_role"],
        state=state,
    )
    print(f"  -> {real_path}")

    # Correct for office version
    print("Applying ArbZG corrections for office version...")
    hours_per_day = config["hours_per_week"] / 5
    corrected = azg.correct_for_office(days, state, hours_per_day=hours_per_day)
    # Compare only actual working days (exclude Urlaub/Krank/Gleittag which track absence hours)
    absence_types = {"Urlaub", "Krank", "Gleittag"}
    total_work_orig = sum(
        d.actual_hours for d, c in zip(days, corrected)
        if d.actual_hours > 0 and c.day_type not in absence_types
    )
    total_corr_work = sum(
        d.corrected_hours for d in corrected
        if d.day_type not in absence_types
    )
    absence_days = sum(1 for d in corrected if d.day_type in absence_types)
    print(f"  Working hours: {total_work_orig:.1f}h -> Corrected: {total_corr_work:.1f}h (delta: {total_corr_work - total_work_orig:.1f}h)")
    if absence_days:
        print(f"  Absence days (Urlaub/Krank/Gleittag): {absence_days} ({absence_days * hours_per_day:.1f}h credited as Ist=Soll)")

    # Generate office report
    print("Generating office report...")
    office_path = excel_office.generate(
        year, corrected,
        output_dir=config["output_dir_office"],
        employee_name=config["employee_name"],
        employee_role=config["employee_role"],
        state=state,
    )
    print(f"  -> {office_path}")
    print("Done.")


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
    # Only count days that have actual time entries (or are Urlaub/Krank/Gleittag).
    # Empty weekdays (no Solidtime entries) are NOT counted as deficit.
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
            elif day_type in ("Krank", "Gleittag"):
                total_actual += hours_per_day
                total_target += hours_per_day
            elif d.actual_hours > 0:
                # Working day with entries
                total_actual += d.actual_hours
                total_target += hours_per_day
            # else: empty weekday - skip entirely (no target, no actual)

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

    # Vacation: count current year only for remaining days
    yearly_vacation = sum(1 for d in corrected if d.date.month <= month and d.day_type == "Urlaub")

    summary = {
        "actual": month_actual,
        "target": month_target,
        "overtime_total": total_overtime,
        "vacation_remaining": config["vacation_days"] - yearly_vacation,
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
