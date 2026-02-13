"""
Database access for Solidtime PostgreSQL.
"""
import os
from datetime import date, datetime
from dataclasses import dataclass

import psycopg2
import psycopg2.extras


@dataclass
class TimeEntry:
    id: str
    start: datetime
    end: datetime
    description: str
    project_name: str
    hours: float


def get_connection():
    return psycopg2.connect(
        host=os.environ["DB_HOST"],
        port=int(os.environ.get("DB_PORT", "5432")),
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASS"],
    )


def fetch_entries(start_date: date, end_date: date) -> list[TimeEntry]:
    """Fetch all time entries for the configured member/client in date range."""
    member_id = os.environ["MEMBER_ID"]
    client_id = os.environ.get("MHB_CLIENT_ID")

    query = """
        SELECT
            te.id,
            te.start,
            te.end,
            te.description,
            COALESCE(p.name, '') as project_name,
            EXTRACT(EPOCH FROM (te.end - te.start)) / 3600.0 as hours
        FROM time_entries te
        LEFT JOIN projects p ON te.project_id = p.id
        WHERE te.member_id = %s
          AND te.end IS NOT NULL
          AND te.start >= %s
          AND te.start < %s
    """
    params = [member_id, start_date, end_date + __import__("datetime").timedelta(days=1)]

    if client_id:
        query += " AND te.client_id = %s"
        params.append(client_id)

    query += " ORDER BY te.start"

    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, params)
            rows = cur.fetchall()
    finally:
        conn.close()

    return [
        TimeEntry(
            id=str(row["id"]),
            start=row["start"],
            end=row["end"],
            description=row["description"],
            project_name=row["project_name"],
            hours=float(row["hours"]),
        )
        for row in rows
    ]


def fetch_daily_summary(start_date: date, end_date: date) -> dict[date, float]:
    """Fetch total hours per day."""
    entries = fetch_entries(start_date, end_date)
    daily: dict[date, float] = {}
    for e in entries:
        d = e.start.date()
        daily[d] = daily.get(d, 0.0) + e.hours
    return daily
