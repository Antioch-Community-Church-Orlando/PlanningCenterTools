"""Copy a plan template's people onto plans via the documented import action.

POST /services/v2/service_types/{st}/plans/{plan}/import with copy_people
copies team members and needed positions from a Plan or PlanTemplate.
Extra targets go in additional_target_ids (imported asynchronously).
Docs: https://api.planningcenteronline.com/docs/apps/services/versions/2018-11-01/vertices/plan (Actions)
"""
from __future__ import annotations

import pypco

from pco.client import _iterate_to_list, get_future_plans, pick_service_type
from pco.models import Plan
from services.write.common import confirm_apply


def get_plan_templates(pco: pypco.PCO, service_type_id: str) -> list[dict]:
    """GET /services/v2/service_types/{id}/plan_templates"""
    return _iterate_to_list(pco, f"/services/v2/service_types/{service_type_id}/plan_templates")


def build_import_payload(source_id: str, additional_target_ids: list[str]) -> dict:
    return {
        "data": {
            "type": "PlanImport",
            "attributes": {
                "source_id": int(source_id),
                "copy_people": True,
                "additional_target_ids": [int(i) for i in additional_target_ids],
            },
        }
    }


def _pick_template(templates: list[dict]) -> dict:
    print("Choose a template:")
    for i, t in enumerate(templates, 1):
        print(f"  {i}. {t['attributes'].get('name') or t['id']}")
    try:
        return templates[int(input("Enter the number of your choice: ")) - 1]
    except (IndexError, ValueError):
        print("Invalid choice. Please enter a number from the list.")
        return _pick_template(templates)


def _pick_target_plans(plans: list[Plan]) -> list[Plan]:
    print("Upcoming plans:")
    for i, plan in enumerate(plans, 1):
        print(f"  {i}. {plan.sort_date.date()}  {plan.dates}")
    raw = input("Enter plan numbers to copy into (comma-separated, or 'all'): ").strip()
    if raw.lower() == "all":
        return plans
    try:
        picks = [plans[int(tok) - 1] for tok in raw.split(",") if tok.strip()]
        if picks:
            return picks
    except (IndexError, ValueError):
        pass
    print("Invalid selection.")
    return _pick_target_plans(plans)


def template_copy(pco: pypco.PCO) -> None:
    """Interactive flow: copy template people into one or more upcoming plans."""
    service_type = pick_service_type(pco)
    st_id = service_type["id"]

    templates = get_plan_templates(pco, st_id)
    if not templates:
        print("✗ This service type has no plan templates.")
        return
    template = _pick_template(templates)

    plans = [Plan.from_api(p, st_id) for p in get_future_plans(pco, st_id)]
    if not plans:
        print("✗ No upcoming plans to copy into.")
        return
    targets = _pick_target_plans(plans)

    template_name = template["attributes"].get("name") or template["id"]
    preview = [f"→ copy people from {template_name!r} into {p.sort_date.date()} {p.dates}" for p in targets]
    if not confirm_apply(preview, "plan imports"):
        print("Aborted — nothing was changed.")
        return

    first, rest = targets[0], targets[1:]
    payload = build_import_payload(template["id"], [p.id for p in rest])
    endpoint = f"/services/v2/service_types/{st_id}/plans/{first.id}/import"
    try:
        pco.post(endpoint, payload=payload)
    except Exception as e:
        print(f"✗ Import failed: {e}")
        return

    print(f"  ✓ Imported into {first.sort_date.date()}")
    for p in rest:
        print(f"  ✓ Queued import into {p.sort_date.date()} (processed asynchronously by PCO)")
    print(f"\n✓ Copied {template_name!r} people into {len(targets)} plan(s).")
