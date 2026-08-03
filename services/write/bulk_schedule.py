"""Bulk scheduling: create PlanPerson records from a CSV.

There is no "schedule_requests" resource in the PCO API — scheduling someone
is a POST of a PlanPerson to the plan's team_members path:
https://api.planningcenteronline.com/docs/apps/services/versions/2018-11-01/vertices/plan_person
"""
from __future__ import annotations

import pypco

from pco.cli import pick_input
from pco.client import (
    get_all_services_people,
    get_future_plans,
    get_teams,
    pick_service_type,
)
from pco.models import Plan
from pco.names import find_person
from services.write.common import confirm_apply


def build_plan_person_payload(
    person_id: str, team_id: str, position: str, notify: bool
) -> dict:
    """JSON:API payload for POST .../plans/{id}/team_members."""
    attributes: dict = {"status": "U"}
    if position:
        attributes["team_position_name"] = position
    if notify:
        attributes["prepare_notification"] = True
    return {
        "data": {
            "type": "PlanPerson",
            "attributes": attributes,
            "relationships": {
                "person": {"data": {"type": "Person", "id": person_id}},
                "team": {"data": {"type": "Team", "id": team_id}},
            },
        }
    }


def match_rows(
    rows: list[dict], people: list[dict], plans: list[Plan], teams: list[dict]
) -> tuple[list[dict], list[str]]:
    """Resolve CSV rows to (person, plan, team) triples.

    Expected CSV columns: ``Full Name``, ``Date`` (YYYY-MM-DD), ``Team``,
    and optional ``Position``.

    Returns:
        (resolved, problems) — resolved rows carry person_id/plan_id/team_id.
    """
    plans_by_date: dict[str, Plan] = {}
    for plan in plans:
        plans_by_date.setdefault(plan.sort_date.date().isoformat(), plan)
    teams_by_name = {t["attributes"]["name"].lower(): t for t in teams}

    resolved: list[dict] = []
    problems: list[str] = []
    for row in rows:
        name = (row.get("Full Name") or "").strip()
        date = (row.get("Date") or "").strip()
        team_name = (row.get("Team") or "").strip()
        position = (row.get("Position") or "").strip()
        if not name:
            continue

        person = find_person(name, people)
        if person is None:
            problems.append(f"✗ {name}: no matching person in Services")
            continue
        plan = plans_by_date.get(date)
        if plan is None:
            problems.append(f"✗ {name}: no upcoming plan on {date!r}")
            continue
        team = teams_by_name.get(team_name.lower())
        if team is None:
            problems.append(f"✗ {name}: unknown team {team_name!r}")
            continue

        resolved.append(
            {
                "person_name": person["attributes"]["full_name"],
                "person_id": person["id"],
                "plan": plan,
                "team_id": team["id"],
                "team_name": team["attributes"]["name"],
                "position": position,
            }
        )
    return resolved, problems


def bulk_schedule(pco: pypco.PCO) -> None:
    """Interactive flow: schedule people onto plans from a CSV.

    CSV columns: Full Name, Date (YYYY-MM-DD), Team, Position (optional).
    See input/ExampleBulkSchedule.csv.example.
    """
    service_type = pick_service_type(pco)
    st_id = service_type["id"]
    rows = pick_input()

    print("Loading people, plans and teams…")
    people = get_all_services_people(pco)
    plans = [Plan.from_api(p, st_id) for p in get_future_plans(pco, st_id)]
    teams = get_teams(pco, st_id)

    resolved, problems = match_rows(rows, people, plans, teams)
    for p in problems:
        print(f"  {p}")

    notify = input("Send scheduling notification emails? [y/N]: ").strip().lower() in ("y", "yes")

    preview = [
        f"→ {r['person_name']} → {r['plan'].sort_date.date()} / {r['team_name']}"
        + (f" ({r['position']})" if r["position"] else "")
        for r in resolved
    ]
    if not confirm_apply(preview, "scheduling requests"):
        print("Aborted — nothing was changed.")
        return

    created = errors = 0
    for r in resolved:
        payload = build_plan_person_payload(r["person_id"], r["team_id"], r["position"], notify)
        endpoint = f"/services/v2/service_types/{st_id}/plans/{r['plan'].id}/team_members"
        try:
            pco.post(endpoint, payload=payload)
            print(f"  ✓ Scheduled {r['person_name']} on {r['plan'].sort_date.date()}")
            created += 1
        except Exception as e:  # surface, count, and continue with remaining rows
            print(f"  ✗ {r['person_name']}: {e}")
            errors += 1

    print(f"\n── Summary ──\n  Created: {created}\n  Errors:  {errors}\n  Unmatched rows: {len(problems)}")
