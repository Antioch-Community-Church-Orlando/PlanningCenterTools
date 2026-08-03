"""Shared helpers for report modules: plan/member fetching and progress output."""
from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta

import pypco

from pco.client import get_future_plans, get_team_members
from pco.models import Plan, PlanPerson


def progress(current: int, total: int, label: str) -> None:
    """Print a single-line progress indicator (overwritten in place)."""
    sys.stdout.write(f"\r  Fetching {label}: {current}/{total}…")
    sys.stdout.flush()
    if current == total:
        sys.stdout.write("\n")


def fetch_upcoming_plans(
    pco: pypco.PCO, service_types: list[dict], weeks: int
) -> list[Plan]:
    """Fetch upcoming plans across service types, limited to a horizon in weeks."""
    cutoff = datetime.now(UTC) + timedelta(weeks=weeks)
    plans: list[Plan] = []
    for st in service_types:
        for raw in get_future_plans(pco, st["id"]):
            plan = Plan.from_api(
                raw, service_type_id=st["id"], service_type_name=st["attributes"]["name"]
            )
            if plan.sort_date <= cutoff:
                plans.append(plan)
    return plans


def fetch_plan_people(
    pco: pypco.PCO,
    plans: list[Plan],
    filter: str | None = "not_archived",
    label: str = "plan people",
) -> list[PlanPerson]:
    """Fetch PlanPerson records for every plan, with a progress indicator."""
    members: list[PlanPerson] = []
    total = len(plans)
    for i, plan in enumerate(plans, 1):
        progress(i, total, label)
        for raw in get_team_members(pco, plan.service_type_id, plan.id, filter=filter):
            members.append(
                PlanPerson.from_api(
                    raw,
                    plan_id=plan.id,
                    plan_date=plan.sort_date,
                    service_type_id=plan.service_type_id,
                    service_type_name=plan.service_type_name,
                )
            )
    return members
