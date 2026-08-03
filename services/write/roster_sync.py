"""Bulk team roster sync via PersonTeamPositionAssignment records.

Team membership is managed through PTPA records under a TeamPosition:
POST/DELETE /services/v2/service_types/{st}/team_positions/{tp}/person_team_position_assignments
https://api.planningcenteronline.com/docs/apps/services/versions/2018-11-01/vertices/person_team_position_assignment
"""
from __future__ import annotations

import pypco

from pco.cli import pick_input
from pco.client import (
    get_all_services_people,
    get_team_position_assignments,
    get_team_positions,
    get_teams,
    pick_service_type,
    rel_id,
)
from pco.names import find_person
from services.write.common import confirm_apply


def _pick_from(items: list[dict], label: str) -> dict:
    print(f"Choose a {label}:")
    for i, item in enumerate(items, 1):
        print(f"  {i}. {item['attributes']['name']}")
    try:
        return items[int(input("Enter the number of your choice: ")) - 1]
    except (IndexError, ValueError):
        print("Invalid choice. Please enter a number from the list.")
        return _pick_from(items, label)


def diff_roster(
    csv_person_ids: dict[str, str], current: list[dict]
) -> tuple[list[tuple[str, str]], list[tuple[str, str, str]]]:
    """Compute roster changes.

    Args:
        csv_person_ids: person_id → display name from the CSV.
        current: PTPA resource dicts currently on the position.

    Returns:
        (to_add, to_remove) — to_add is (person_id, name); to_remove is
        (assignment_id, person_id, name-ish).
    """
    current_by_person = {rel_id(a, "person"): a for a in current}
    to_add = [(pid, name) for pid, name in csv_person_ids.items() if pid not in current_by_person]
    to_remove = [
        (a["id"], pid, pid)
        for pid, a in current_by_person.items()
        if pid and pid not in csv_person_ids
    ]
    return to_add, to_remove


def roster_sync(pco: pypco.PCO) -> None:
    """Sync a team position's roster to a CSV (column: Full Name).

    Adds people in the CSV who aren't assigned; removes assignments for
    people not in the CSV. Removals require typed confirmation.
    """
    service_type = pick_service_type(pco)
    st_id = service_type["id"]
    team = _pick_from(get_teams(pco, st_id), "team")
    positions = get_team_positions(pco, team["id"])
    if not positions:
        print("✗ This team has no positions; create one in Planning Center first.")
        return
    position = _pick_from(positions, "team position")

    rows = pick_input()
    people = get_all_services_people(pco)
    id_to_name: dict[str, str] = {}
    unmatched: list[str] = []
    for row in rows:
        name = (row.get("Full Name") or "").strip()
        if not name:
            continue
        person = find_person(name, people)
        if person is None:
            unmatched.append(name)
        else:
            id_to_name[person["id"]] = person["attributes"]["full_name"]
    for name in unmatched:
        print(f"  ✗ No match for {name!r} — row skipped")

    all_assignments = get_team_position_assignments(pco, team["id"])
    current = [a for a in all_assignments if rel_id(a, "team_position") == position["id"]]
    person_names = {p["id"]: p["attributes"]["full_name"] for p in people}

    to_add, to_remove = diff_roster(id_to_name, current)
    preview = [f"+ add    {name}" for _, name in to_add] + [
        f"− remove {person_names.get(pid, pid)}" for _, pid, _ in to_remove
    ]
    if not confirm_apply(preview, "roster assignments", destructive=bool(to_remove)):
        print("Aborted — nothing was changed.")
        return

    base = f"/services/v2/service_types/{st_id}/team_positions/{position['id']}/person_team_position_assignments"
    added = removed = errors = 0
    for pid, name in to_add:
        payload = {
            "data": {
                "type": "PersonTeamPositionAssignment",
                "attributes": {"person_id": pid},
            }
        }
        try:
            pco.post(base, payload=payload)
            print(f"  ✓ Added {name}")
            added += 1
        except Exception as e:
            print(f"  ✗ Add {name}: {e}")
            errors += 1
    for assignment_id, pid, _ in to_remove:
        try:
            pco.delete(f"{base}/{assignment_id}")
            print(f"  ✓ Removed {person_names.get(pid, pid)}")
            removed += 1
        except Exception as e:
            print(f"  ✗ Remove {person_names.get(pid, pid)}: {e}")
            errors += 1

    print(f"\n── Summary ──\n  Added: {added}\n  Removed: {removed}\n  Errors: {errors}")
