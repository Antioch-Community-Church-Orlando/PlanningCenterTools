"""Open positions / coverage report.

A NeededPosition is *already* an amount of unfilled positions — its
``quantity`` attribute is the open-slot count. We report it directly.
"""
from __future__ import annotations

import pypco

from pco import report
from pco.client import get_needed_positions, get_teams, pick_service_types
from pco.config import get_config
from pco.models import NeededPosition
from services.reports.common import fetch_upcoming_plans, progress


def coverage_report(pco: pypco.PCO) -> None:
    """Report open (needed) positions across upcoming plans."""
    cfg = get_config()
    service_types = pick_service_types(pco)
    plans = fetch_upcoming_plans(pco, service_types, cfg.thresholds.schedule_horizon_weeks)

    team_names: dict[str, str] = {}
    for st in service_types:
        for team in get_teams(pco, st["id"]):
            team_names[team["id"]] = team["attributes"]["name"]

    records = []
    for i, plan in enumerate(plans, 1):
        progress(i, len(plans), "needed positions")
        for raw in get_needed_positions(pco, plan.service_type_id, plan.id):
            np = NeededPosition.from_api(raw, plan_id=plan.id)
            if np.quantity <= 0:
                continue
            records.append(
                {
                    "date": plan.sort_date.date().isoformat(),
                    "service_type": plan.service_type_name,
                    "plan_dates": plan.dates,
                    "team": team_names.get(np.team_id, np.team_id),
                    "position": np.position_name,
                    "open_slots": np.quantity,
                }
            )

    total_open = sum(r["open_slots"] for r in records)
    print(f"\nScanned {len(plans)} upcoming plans.")
    if not records:
        print("✓ No open positions — everything is covered.")
    for r in records:
        print(
            f"  ✗ {r['date']} {r['service_type']} — {r['team']} / {r['position']}:"
            f" {r['open_slots']} open"
        )

    out = report.write(
        "coverage",
        records,
        fields=["date", "service_type", "plan_dates", "team", "position", "open_slots"],
        summary_lines=[
            f"Plans scanned: {len(plans)}",
            f"Total open slots: {total_open}",
            "",
        ]
        + [f"- {r['date']} {r['team']}/{r['position']}: {r['open_slots']}" for r in records],
        scope=", ".join(st["attributes"]["name"] for st in service_types),
    )
    print(f"✓ Report written to {out}/coverage.*")
