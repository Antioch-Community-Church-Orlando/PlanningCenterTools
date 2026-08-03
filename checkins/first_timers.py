"""First-time visitor report from Check-Ins.

Uses the documented ``?filter=first_time`` scope: check-ins that are the
person's first for a given event.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pypco

from pco import report
from pco.checkins_api import iter_event_check_ins, pick_event


def collect_first_timers(records, cutoff_iso: str) -> list[dict]:
    """Collect first-time check-ins newer than cutoff from an iterator.

    Records arrive newest-first, so we stop as soon as one is older than the
    cutoff — no need to page through years of history.
    """
    rows = []
    for rec in records:
        check_in = rec["data"]
        created = check_in["attributes"].get("created_at") or ""
        if created and created < cutoff_iso:
            break
        person_name = next(
            (
                inc["attributes"].get("name", "")
                for inc in rec.get("included", [])
                if inc.get("type") == "Person"
            ),
            "",
        ) or f"{check_in['attributes'].get('first_name', '')} {check_in['attributes'].get('last_name', '')}".strip()
        rows.append({"person_name": person_name, "checked_in_at": created[:10]})
    return rows


def first_time_visitors(pco: pypco.PCO) -> None:
    """Report first-time check-ins for an event over a recent window."""
    event = pick_event(pco)
    raw_days = input("How many days back? [30]: ").strip()
    days = int(raw_days) if raw_days.isdigit() else 30
    cutoff = (datetime.now(UTC) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")

    print("Fetching first-time check-ins…")
    rows = collect_first_timers(
        iter_event_check_ins(pco, event["id"], filter="first_time"), cutoff
    )

    event_name = event["attributes"]["name"]
    print(f"\nFirst-time visitors at {event_name!r} in the last {days} days: {len(rows)}")
    for r in rows:
        print(f"  ✓ {r['person_name']} — {r['checked_in_at']}")

    out = report.write(
        "first_time_visitors",
        rows,
        fields=["person_name", "checked_in_at"],
        summary_lines=[f"Event: {event_name}", f"First-time visitors: {len(rows)}"],
        scope=event_name,
        date_range=(cutoff[:10], datetime.now(UTC).date().isoformat()),
    )
    print(f"✓ Report written to {out}/first_time_visitors.*")
