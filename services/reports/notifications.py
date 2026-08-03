"""Scheduling-notification audit.

Reports unconfirmed volunteers on upcoming plans whose scheduling notification
was never sent, or was sent but never read — the people most likely to no-show
because they don't know they're scheduled.
"""
from __future__ import annotations

import pypco

from pco import report
from pco.client import pick_service_types
from pco.config import get_config
from pco.models import PlanPerson
from services.reports.common import fetch_plan_people, fetch_upcoming_plans


def audit_notifications(members: list[PlanPerson]) -> list[dict]:
    records = []
    for m in members:
        if not m.person_id or not m.is_unconfirmed or not m.plan_date:
            continue
        if m.notification_sent_at is None:
            issue = "notification never sent"
        elif m.notification_read_at is None:
            issue = "notification sent but unread"
        else:
            continue
        records.append(
            {
                "person_id": m.person_id,
                "person_name": m.person_name,
                "date": m.plan_date.date().isoformat(),
                "service_type": m.service_type_name,
                "team": m.team_name or m.position,
                "issue": issue,
                "sent_at": m.notification_sent_at.isoformat() if m.notification_sent_at else "",
            }
        )
    records.sort(key=lambda r: r["date"])
    return records


def notification_audit(pco: pypco.PCO) -> None:
    """Report pending volunteers with missing/unread scheduling notifications."""
    cfg = get_config()
    service_types = pick_service_types(pco)
    plans = fetch_upcoming_plans(pco, service_types, cfg.thresholds.schedule_horizon_weeks)
    members = fetch_plan_people(pco, plans, filter="not_archived", label="assignments")

    records = audit_notifications(members)

    never_sent = sum(1 for r in records if r["issue"] == "notification never sent")
    unread = len(records) - never_sent
    print(f"\nScanned {len(plans)} upcoming plans.")
    if not records:
        print("✓ Every pending volunteer has been notified and has seen it.")
    for r in records:
        print(f"  ⚠  {r['person_name']} ({r['date']}, {r['team']}): {r['issue']}")

    out = report.write(
        "notification_audit",
        records,
        fields=["person_name", "date", "service_type", "team", "issue", "sent_at"],
        summary_lines=[
            f"Pending volunteers with notification issues: {len(records)}",
            f"- never sent: {never_sent}",
            f"- sent but unread: {unread}",
        ],
        scope=", ".join(st["attributes"]["name"] for st in service_types),
    )
    print(f"✓ Report written to {out}/notification_audit.*")
