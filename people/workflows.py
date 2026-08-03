"""Workflow card tools: bulk enrollment and cross-workflow overdue report.

Docs: https://api.planningcenteronline.com/docs/apps/people/versions/2024-09-12/vertices/workflow_card
"""
from __future__ import annotations

import pypco

from pco import report
from pco.cli import pick_input
from pco.names import find_person
from pco.people_api import (
    create_workflow_card,
    get_overdue_cards,
    get_workflows,
)
from services.write.common import confirm_apply


def _pick_workflow(workflows: list[dict]) -> dict:
    print("Choose a workflow:")
    for i, wf in enumerate(workflows, 1):
        print(f"  {i}. {wf['attributes']['name']}")
    try:
        return workflows[int(input("Enter the number of your choice: ")) - 1]
    except (IndexError, ValueError):
        print("Invalid choice. Please enter a number from the list.")
        return _pick_workflow(workflows)


def bulk_enroll_workflow(pco: pypco.PCO) -> None:
    """Enroll people from a CSV (column: Full Name) into a workflow."""
    from pco.people_api import get_all_people

    workflows = get_workflows(pco)
    if not workflows:
        print("✗ No workflows found in People.")
        return
    workflow = _pick_workflow(workflows)
    rows = pick_input()

    print("Fetching People profiles…")
    people = get_all_people(pco)

    matched: list[dict] = []
    unmatched: list[str] = []
    for row in rows:
        name = (row.get("Full Name") or "").strip()
        if not name:
            continue
        person = find_person(name, people)
        if person is None:
            unmatched.append(name)
        else:
            matched.append(person)
    for name in unmatched:
        print(f"  ✗ No match for {name!r} — row skipped")

    wf_name = workflow["attributes"]["name"]
    preview = [
        f"→ add {p['attributes'].get('name') or p['attributes'].get('full_name', p['id'])}"
        f" to workflow {wf_name!r}"
        for p in matched
    ]
    if not confirm_apply(preview, "workflow cards"):
        print("Aborted — nothing was changed.")
        return

    created = errors = 0
    for p in matched:
        try:
            create_workflow_card(pco, workflow["id"], p["id"])
            created += 1
        except Exception as e:
            print(f"  ✗ {p['attributes'].get('name', p['id'])}: {e}")
            errors += 1

    print(f"\n── Summary ──\n  Cards created: {created}\n  Errors: {errors}\n  Unmatched: {len(unmatched)}")


def overdue_cards_report(pco: pypco.PCO) -> None:
    """Cross-workflow report of overdue workflow cards."""
    workflows = get_workflows(pco)
    if not workflows:
        print("✗ No workflows found in People.")
        return

    records = []
    for wf in workflows:
        wf_name = wf["attributes"]["name"]
        for rec in get_overdue_cards(pco, wf["id"]):
            card = rec["data"]
            person_name = next(
                (
                    inc["attributes"].get("name", "")
                    for inc in rec.get("included", [])
                    if inc.get("type") == "Person"
                ),
                "",
            )
            records.append(
                {
                    "workflow": wf_name,
                    "person_name": person_name,
                    "stage": card["attributes"].get("stage", ""),
                    "due_at": card["attributes"].get("calculated_due_at_in_days_ago", ""),
                    "created_at": card["attributes"].get("created_at", ""),
                }
            )

    print(f"\nChecked {len(workflows)} workflows.")
    if not records:
        print("✓ No overdue workflow cards.")
    for r in records:
        print(f"  ⚠  [{r['workflow']}] {r['person_name']} — overdue")

    out = report.write(
        "overdue_cards",
        records,
        fields=["workflow", "person_name", "stage", "due_at", "created_at"],
        summary_lines=[f"Overdue cards: {len(records)}"]
        + [f"- [{r['workflow']}] {r['person_name']}" for r in records],
        scope="All People workflows",
    )
    print(f"✓ Report written to {out}/overdue_cards.*")
