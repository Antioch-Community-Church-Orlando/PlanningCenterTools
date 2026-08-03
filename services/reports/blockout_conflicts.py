"""Blockout vs. schedule conflict scan.

Cross-references upcoming plan assignments against each scheduled person's
blockout windows and reports anyone scheduled during a blockout.
"""
from __future__ import annotations

import pypco

from pco import report
from pco.client import get_person_blockouts, pick_service_types
from pco.config import get_config
from pco.models import Blockout, PlanPerson
from services.reports.common import fetch_plan_people, fetch_upcoming_plans, progress


def find_conflicts(
    members: list[PlanPerson], blockouts_by_person: dict[str, list[Blockout]]
) -> list[dict]:
    records = []
    for m in members:
        if not m.person_id or not m.plan_date or m.is_declined:
            continue
        for bo in blockouts_by_person.get(m.person_id, []):
            if bo.contains(m.plan_date):
                records.append(
                    {
                        "person_id": m.person_id,
                        "person_name": m.person_name,
                        "date": m.plan_date.date().isoformat(),
                        "service_type": m.service_type_name,
                        "team": m.team_name or m.position,
                        "status": m.status,
                        "blockout_reason": bo.reason,
                        "blockout_window": f"{bo.starts_at.date()} → {bo.ends_at.date()}",
                    }
                )
                break
    return records


def scan_blockout_conflicts(pco: pypco.PCO) -> None:
    """Report people scheduled (confirmed or pending) during their blockouts."""
    cfg = get_config()
    service_types = pick_service_types(pco)
    plans = fetch_upcoming_plans(pco, service_types, cfg.thresholds.schedule_horizon_weeks)
    members = fetch_plan_people(pco, plans, filter="not_archived", label="assignments")

    person_ids = sorted({m.person_id for m in members if m.person_id})
    blockouts_by_person: dict[str, list[Blockout]] = {}
    for i, pid in enumerate(person_ids, 1):
        progress(i, len(person_ids), "blockouts")
        blockouts_by_person[pid] = [
            Blockout.from_api(raw, person_id=pid) for raw in get_person_blockouts(pco, pid)
        ]

    records = find_conflicts(members, blockouts_by_person)

    print(f"\nChecked {len(person_ids)} scheduled people across {len(plans)} plans.")
    if not records:
        print("✓ No blockout conflicts found.")
    for r in records:
        print(
            f"  ⚠  {r['person_name']} is scheduled on {r['date']} ({r['team']})"
            f" but blocked out {r['blockout_window']}"
            + (f" — {r['blockout_reason']}" if r["blockout_reason"] else "")
        )

    out = report.write(
        "blockout_conflicts",
        records,
        fields=[
            "person_name",
            "date",
            "service_type",
            "team",
            "status",
            "blockout_window",
            "blockout_reason",
        ],
        summary_lines=[f"Conflicts found: {len(records)}"]
        + [f"- {r['person_name']} on {r['date']}" for r in records],
        scope=", ".join(st["attributes"]["name"] for st in service_types),
    )
    print(f"✓ Report written to {out}/blockout_conflicts.*")
