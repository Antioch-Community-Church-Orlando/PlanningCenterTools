"""Decline / no-response detector.

Aggregates PlanPerson records (URL segment: team_members) over a lookback
window and flags volunteers whose decline rate or pending (no-response) rate
crosses the configured thresholds.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pypco

from pco import report
from pco.client import get_plans_between, pick_service_types
from pco.config import get_config
from pco.models import Plan, PlanPerson
from services.reports.common import fetch_plan_people, progress


def _collect(members: list[PlanPerson]) -> list[dict]:
    """Aggregate per-person request/decline/pending counts."""
    per_person: dict[str, dict] = {}
    for m in members:
        if not m.person_id:
            continue  # unassigned placeholder slots
        rec = per_person.setdefault(
            m.person_id,
            {
                "person_id": m.person_id,
                "person_name": m.person_name,
                "requests": 0,
                "declines": 0,
                "pending": 0,
                "confirmed": 0,
                "decline_reasons": [],
                "last_declined_at": None,
            },
        )
        rec["requests"] += 1
        if m.is_declined:
            rec["declines"] += 1
            if m.decline_reason:
                rec["decline_reasons"].append(m.decline_reason)
            if m.status_updated_at and (
                rec["last_declined_at"] is None or m.status_updated_at > rec["last_declined_at"]
            ):
                rec["last_declined_at"] = m.status_updated_at
        elif m.is_unconfirmed:
            rec["pending"] += 1
        elif m.is_confirmed:
            rec["confirmed"] += 1

    records = []
    for rec in per_person.values():
        rec["decline_rate"] = round(rec["declines"] / rec["requests"], 2)
        rec["pending_rate"] = round(rec["pending"] / rec["requests"], 2)
        rec["decline_reasons"] = "; ".join(rec["decline_reasons"][:5])
        records.append(rec)
    return records


def scan_decline_rates(pco: pypco.PCO) -> None:
    """Report volunteers with high decline or no-response rates."""
    cfg = get_config()
    service_types = pick_service_types(pco)
    lookback = cfg.thresholds.decline_lookback_days
    now = datetime.now(UTC)
    after = (now - timedelta(days=lookback)).strftime("%Y-%m-%dT%H:%M:%SZ")
    before = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    plans: list[Plan] = []
    total = len(service_types)
    for i, st in enumerate(service_types, 1):
        progress(i, total, "plans")
        for raw in get_plans_between(pco, st["id"], after, before):
            plans.append(Plan.from_api(raw, st["id"], st["attributes"]["name"]))

    members = fetch_plan_people(pco, plans, filter="not_archived", label="scheduling requests")
    records = _collect(members)

    min_requests = 2
    flagged = sorted(
        (
            r
            for r in records
            if r["requests"] >= min_requests
            and (
                r["decline_rate"] >= cfg.thresholds.decline_rate_threshold
                or r["pending_rate"] >= cfg.thresholds.pending_rate_threshold
            )
        ),
        key=lambda r: (-r["decline_rate"], -r["pending_rate"]),
    )

    print(f"\nScanned {len(plans)} plans over the last {lookback} days.")
    if not flagged:
        print("✓ No volunteers over the decline/no-response thresholds.")
    for r in flagged:
        print(
            f"  ⚠  {r['person_name']}: {r['declines']}/{r['requests']} declined"
            f" ({r['decline_rate']:.0%}), {r['pending']} pending ({r['pending_rate']:.0%})"
            + (f" — reasons: {r['decline_reasons']}" if r["decline_reasons"] else "")
        )

    summary = [
        f"Volunteers scanned: {len(records)}",
        f"Flagged: {len(flagged)} (decline rate ≥ {cfg.thresholds.decline_rate_threshold:.0%}"
        f" or pending rate ≥ {cfg.thresholds.pending_rate_threshold:.0%})",
        "",
    ] + [
        f"- {r['person_name']}: {r['decline_rate']:.0%} declined, {r['pending_rate']:.0%} pending"
        for r in flagged
    ]
    out = report.write(
        "decline_report",
        sorted(records, key=lambda r: -r["decline_rate"]),
        fields=[
            "person_name",
            "requests",
            "confirmed",
            "declines",
            "pending",
            "decline_rate",
            "pending_rate",
            "last_declined_at",
            "decline_reasons",
        ],
        summary_lines=summary,
        scope=", ".join(st["attributes"]["name"] for st in service_types),
        date_range=(after[:10], before[:10]),
    )
    print(f"✓ Report written to {out}/decline_report.*")
