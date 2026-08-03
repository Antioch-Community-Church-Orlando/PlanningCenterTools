"""Cross-service duplicate scan.

Finds people **confirmed** in more than one plan on the same calendar date
(e.g. scheduled at two campuses/services at once). Multiple positions within
the same plan are NOT flagged here — that's normal (see the in-plan duplicate
check in services/volunteers.py).
"""
from __future__ import annotations

import pypco

from pco import report
from pco.client import pick_service_types
from pco.config import get_config
from pco.models import PlanPerson
from services.reports.common import fetch_plan_people, fetch_upcoming_plans


def find_cross_duplicates(members: list[PlanPerson]) -> list[dict]:
    """Group confirmed assignments by (person, date); flag multi-plan days."""
    by_person_day: dict[tuple[str, str], list[PlanPerson]] = {}
    for m in members:
        if not m.person_id or not m.is_confirmed or not m.plan_date:
            continue
        key = (m.person_id, m.plan_date.date().isoformat())
        by_person_day.setdefault(key, []).append(m)

    records = []
    for (person_id, day), assignments in sorted(by_person_day.items(), key=lambda kv: kv[0][1]):
        plan_ids = {a.plan_id for a in assignments}
        if len(plan_ids) < 2:
            continue
        records.append(
            {
                "person_id": person_id,
                "person_name": assignments[0].person_name,
                "date": day,
                "plan_count": len(plan_ids),
                "assignments": "; ".join(
                    f"{a.service_type_name} — {a.team_name or a.position}" for a in assignments
                ),
            }
        )
    return records


def scan_cross_duplicates(pco: pypco.PCO) -> None:
    """Report volunteers confirmed on multiple plans on the same day."""
    cfg = get_config()
    service_types = pick_service_types(pco)
    plans = fetch_upcoming_plans(pco, service_types, cfg.thresholds.schedule_horizon_weeks)
    members = fetch_plan_people(pco, plans, filter="confirmed", label="confirmed assignments")

    records = find_cross_duplicates(members)

    print(f"\nScanned {len(plans)} upcoming plans.")
    if not records:
        print("✓ Nobody is double-booked across plans.")
    for r in records:
        print(f"  ⚠  {r['person_name']} on {r['date']}: {r['assignments']}")

    out = report.write(
        "cross_duplicates",
        records,
        fields=["person_name", "date", "plan_count", "assignments"],
        summary_lines=[f"Double-booked volunteer-days: {len(records)}"]
        + [f"- {r['person_name']} on {r['date']}" for r in records],
        scope=", ".join(st["attributes"]["name"] for st in service_types),
    )
    print(f"✓ Report written to {out}/cross_duplicates.*")
