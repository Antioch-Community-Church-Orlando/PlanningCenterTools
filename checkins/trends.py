"""Attendance trend report from Check-Ins event periods.

EventPeriod already carries per-gathering counts (regular/guest/volunteer),
so trends need only one paginated listing per event — no per-person scans.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pypco

from pco import report
from pco.checkins_api import get_event_periods, pick_event

_ROLLING_WINDOW = 4


def build_trend_records(periods: list[dict]) -> list[dict]:
    """Convert EventPeriod resources into trend rows with rolling averages."""
    rows = []
    for p in periods:
        attrs = p["attributes"]
        regular = int(attrs.get("regular_count") or 0)
        guest = int(attrs.get("guest_count") or 0)
        volunteer = int(attrs.get("volunteer_count") or 0)
        rows.append(
            {
                "date": (attrs.get("starts_at") or "")[:10],
                "regular": regular,
                "guest": guest,
                "volunteer": volunteer,
                "total": regular + guest + volunteer,
            }
        )
    rows.sort(key=lambda r: r["date"])

    for i, row in enumerate(rows):
        window = rows[max(0, i - _ROLLING_WINDOW + 1) : i + 1]
        row["rolling_avg_total"] = round(sum(w["total"] for w in window) / len(window), 1)
    return rows


def attendance_trends(pco: pypco.PCO) -> None:
    """Interactive attendance trend report for one Check-Ins event."""
    event = pick_event(pco)
    raw_weeks = input("How many weeks back? [26]: ").strip()
    weeks = int(raw_weeks) if raw_weeks.isdigit() else 26
    cutoff = (datetime.now(UTC) - timedelta(weeks=weeks)).date().isoformat()

    print("Fetching attendance periods…")
    periods = [
        p
        for p in get_event_periods(pco, event["id"])
        if (p["attributes"].get("starts_at") or "") >= cutoff
    ]
    rows = build_trend_records(periods)

    event_name = event["attributes"]["name"]
    print(f"\nAttendance for {event_name!r} (last {weeks} weeks):")
    if not rows:
        print("  No attendance periods found.")
    for r in rows:
        print(
            f"  {r['date']}: {r['total']} total ({r['regular']} regular,"
            f" {r['guest']} guest, {r['volunteer']} volunteer)"
            f" — {_ROLLING_WINDOW}-week avg {r['rolling_avg_total']}"
        )

    if rows:
        avg = round(sum(r["total"] for r in rows) / len(rows), 1)
        ratio_rows = [r for r in rows if r["total"]]
        vol_ratio = (
            round(sum(r["volunteer"] / r["total"] for r in ratio_rows) / len(ratio_rows), 2)
            if ratio_rows
            else 0
        )
        print(f"\n  Average attendance: {avg}   Volunteer share: {vol_ratio:.0%}")

    out = report.write(
        "attendance_trends",
        rows,
        fields=["date", "regular", "guest", "volunteer", "total", "rolling_avg_total"],
        summary_lines=[
            f"Event: {event_name}",
            f"Gatherings analyzed: {len(rows)}",
        ],
        scope=event_name,
        date_range=(cutoff, datetime.now(UTC).date().isoformat()),
    )
    print(f"✓ Report written to {out}/attendance_trends.*")
