"""Auto-blockout from repeated declines.

Finds volunteers with N or more declines in the lookback window and offers to
create a blockout for them (so they stop receiving scheduling requests for a
period). Dry-run preview + explicit confirmation before anything is written.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pypco

from pco.client import get_plans_between, pick_service_types, post_blockout
from pco.config import get_config
from pco.models import Plan
from services.reports.common import fetch_plan_people
from services.write.common import confirm_apply


def find_repeated_decliners(members: list, min_declines: int) -> list[dict]:
    """People with at least *min_declines* declined assignments."""
    per_person: dict[str, dict] = {}
    for m in members:
        if not m.person_id or not m.is_declined:
            continue
        rec = per_person.setdefault(
            m.person_id,
            {"person_id": m.person_id, "person_name": m.person_name, "declines": 0},
        )
        rec["declines"] += 1
    return sorted(
        (r for r in per_person.values() if r["declines"] >= min_declines),
        key=lambda r: -r["declines"],
    )


def auto_blockout_from_declines(pco: pypco.PCO) -> None:
    """Interactive flow: propose blockouts for volunteers who keep declining."""
    cfg = get_config()
    service_types = pick_service_types(pco)
    lookback = cfg.thresholds.decline_lookback_days
    min_declines = cfg.thresholds.repeated_decline_count

    now = datetime.now(UTC)
    after = (now - timedelta(days=lookback)).strftime("%Y-%m-%dT%H:%M:%SZ")
    before = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    plans: list[Plan] = []
    for st in service_types:
        for raw in get_plans_between(pco, st["id"], after, before):
            plans.append(Plan.from_api(raw, st["id"], st["attributes"]["name"]))
    members = fetch_plan_people(pco, plans, filter="not_archived", label="assignments")

    decliners = find_repeated_decliners(members, min_declines)
    if not decliners:
        print(f"✓ Nobody has {min_declines}+ declines in the last {lookback} days.")
        return

    print(f"\nVolunteers with {min_declines}+ declines in the last {lookback} days:")
    for d in decliners:
        print(f"  ⚠  {d['person_name']}: {d['declines']} declines")

    weeks = cfg.thresholds.schedule_horizon_weeks
    raw_weeks = input(f"Blockout length in weeks from today [{weeks}]: ").strip()
    weeks = int(raw_weeks) if raw_weeks.isdigit() else weeks
    starts_at = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    ends_at = (now + timedelta(weeks=weeks)).strftime("%Y-%m-%dT%H:%M:%SZ")
    reason = f"Auto-blockout: {min_declines}+ recent declines (added by PlanningCenterTools)"

    preview = [
        f"→ blockout {d['person_name']} from {starts_at[:10]} to {ends_at[:10]}" for d in decliners
    ]
    if not confirm_apply(preview, "blockouts"):
        print("Aborted — nothing was changed.")
        return

    created = errors = 0
    for d in decliners:
        payload = pco.template(
            "Blockout",
            {
                "reason": reason,
                "repeat_frequency": "no_repeat",
                "starts_at": starts_at,
                "ends_at": ends_at,
                "share": "false",
            },
        )
        try:
            post_blockout(pco, d["person_id"], payload)
            print(f"  ✓ Blocked out {d['person_name']}")
            created += 1
        except Exception as e:
            print(f"  ✗ {d['person_name']}: {e}")
            errors += 1

    print(f"\n── Summary ──\n  Blockouts created: {created}\n  Errors: {errors}")
