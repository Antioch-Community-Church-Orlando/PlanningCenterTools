"""Team roster reports: drift, schedule-preference audit, and onboarding.

Rosters come from the documented endpoints:
  GET /services/v2/teams/{id}/people                              (roster)
  GET /services/v2/teams/{id}/person_team_position_assignments    (positions/preferences)
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pypco

from pco import report
from pco.client import (
    get_plans_between,
    get_team_people,
    get_team_position_assignments,
    get_teams,
    pick_service_types,
)
from pco.config import get_config
from pco.models import Person, Plan, PlanPerson, TeamPositionAssignment
from services.reports.common import fetch_plan_people, progress


def _recent_confirmed(pco: pypco.PCO, service_types: list[dict], days: int) -> list[PlanPerson]:
    now = datetime.now(UTC)
    after = (now - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    before = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    plans: list[Plan] = []
    for st in service_types:
        for raw in get_plans_between(pco, st["id"], after, before):
            plans.append(Plan.from_api(raw, st["id"], st["attributes"]["name"]))
    return fetch_plan_people(pco, plans, filter="confirmed", label="confirmed serves")


def roster_drift_report(pco: pypco.PCO) -> None:
    """Compare team rosters against who actually served recently.

    Flags: roster members with zero confirmed serves in the inactive window,
    and people serving on a team without being on its roster. Also includes
    each roster member's scheduling preference.
    """
    cfg = get_config()
    days = cfg.thresholds.inactive_threshold_days
    service_types = pick_service_types(pco)

    members = _recent_confirmed(pco, service_types, days)
    served_by_team: dict[str, dict[str, str]] = {}
    for m in members:
        if m.person_id and m.team_id:
            served_by_team.setdefault(m.team_id, {})[m.person_id] = m.person_name

    records = []
    for st in service_types:
        teams = get_teams(pco, st["id"])
        for i, team in enumerate(teams, 1):
            progress(i, len(teams), f"{st['attributes']['name']} rosters")
            team_id = team["id"]
            team_name = team["attributes"]["name"]
            roster = {p["id"]: Person.from_api(p) for p in get_team_people(pco, team_id)}
            prefs = {
                a.person_id: a.schedule_preference
                for a in map(TeamPositionAssignment.from_api, get_team_position_assignments(pco, team_id))
            }
            served = served_by_team.get(team_id, {})

            for pid, person in roster.items():
                if pid not in served:
                    records.append(
                        {
                            "service_type": st["attributes"]["name"],
                            "team": team_name,
                            "person_name": person.full_name,
                            "issue": f"on roster, no confirmed serves in {days} days",
                            "schedule_preference": prefs.get(pid, ""),
                        }
                    )
            for pid, name in served.items():
                if pid not in roster:
                    records.append(
                        {
                            "service_type": st["attributes"]["name"],
                            "team": team_name,
                            "person_name": name,
                            "issue": "served recently but not on team roster",
                            "schedule_preference": "",
                        }
                    )

    print(f"\nRoster drift over the last {days} days:")
    if not records:
        print("✓ Rosters match recent serving activity.")
    for r in records:
        print(f"  ⚠  [{r['team']}] {r['person_name']} — {r['issue']}")

    out = report.write(
        "roster_drift",
        records,
        fields=["service_type", "team", "person_name", "issue", "schedule_preference"],
        summary_lines=[f"Drift findings: {len(records)}"]
        + [f"- [{r['team']}] {r['person_name']}: {r['issue']}" for r in records],
        scope=", ".join(st["attributes"]["name"] for st in service_types),
    )
    print(f"✓ Report written to {out}/roster_drift.*")


def onboarding_report(pco: pypco.PCO) -> None:
    """Track new volunteers: first confirmed serve within the new-volunteer window.

    A volunteer's join date is their *first confirmed serve* (roster Person
    created_at is the account creation date — not a join date — so we don't
    use it).
    """
    cfg = get_config()
    new_days = cfg.thresholds.new_volunteer_days
    lookback = max(cfg.thresholds.decline_lookback_days, new_days * 2)
    service_types = pick_service_types(pco)

    members = _recent_confirmed(pco, service_types, lookback)
    first_serve: dict[str, PlanPerson] = {}
    serve_count: dict[str, int] = {}
    for m in sorted(members, key=lambda m: m.plan_date or datetime.now(UTC)):
        if not m.person_id or not m.plan_date:
            continue
        first_serve.setdefault(m.person_id, m)
        serve_count[m.person_id] = serve_count.get(m.person_id, 0) + 1

    cutoff = datetime.now(UTC) - timedelta(days=new_days)
    records = []
    for pid, first in first_serve.items():
        if first.plan_date and first.plan_date >= cutoff:
            records.append(
                {
                    "person_name": first.person_name,
                    "first_served": first.plan_date.date().isoformat(),
                    "team": first.team_name or first.position,
                    "service_type": first.service_type_name,
                    "serves_since": serve_count[pid],
                }
            )
    records.sort(key=lambda r: r["first_served"])

    print(f"\nNew volunteers (first confirmed serve in the last {new_days} days):")
    if not records:
        print("  None found.")
    for r in records:
        print(
            f"  ✓ {r['person_name']} — first served {r['first_served']}"
            f" ({r['team']}), {r['serves_since']} serve(s) since"
        )

    out = report.write(
        "onboarding",
        records,
        fields=["person_name", "first_served", "team", "service_type", "serves_since"],
        summary_lines=[f"New volunteers: {len(records)}"]
        + [f"- {r['person_name']} ({r['first_served']})" for r in records],
        scope=", ".join(st["attributes"]["name"] for st in service_types),
    )
    print(f"✓ Report written to {out}/onboarding.*")
