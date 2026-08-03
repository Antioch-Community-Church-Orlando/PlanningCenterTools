"""Bulk custom-field updates from a CSV.

CSV columns: ``Full Name`` plus one column per custom field to set (the column
header must match the field definition name in People exactly).
"""
from __future__ import annotations

import pypco

from pco import cli
from pco.names import find_person
from pco.people_api import (
    get_all_people,
    get_field_definitions,
    get_person_field_data,
    set_field_datum,
)
from services.write.common import confirm_apply


def plan_updates(
    rows: list[dict], people: list[dict], field_defs: list[dict]
) -> tuple[list[dict], list[str]]:
    """Resolve CSV rows into concrete field updates.

    Returns:
        (updates, problems). Each update: person_id, person_name,
        field_definition_id, field_name, value.
    """
    defs_by_name = {fd["attributes"]["name"].lower(): fd for fd in field_defs}
    updates: list[dict] = []
    problems: list[str] = []

    for row in rows:
        name = (row.get("Full Name") or "").strip()
        if not name:
            continue
        person = find_person(name, people)
        if person is None:
            problems.append(f"✗ {name}: no matching person")
            continue
        for column, value in row.items():
            if column == "Full Name" or value is None or not str(value).strip():
                continue
            fd = defs_by_name.get(column.strip().lower())
            if fd is None:
                problems.append(f"✗ {name}: no field definition named {column!r}")
                continue
            updates.append(
                {
                    "person_id": person["id"],
                    "person_name": person["attributes"].get("name")
                    or person["attributes"].get("full_name", ""),
                    "field_definition_id": fd["id"],
                    "field_name": fd["attributes"]["name"],
                    "value": str(value).strip(),
                }
            )
    return updates, problems


def bulk_update_fields(pco: pypco.PCO) -> None:
    """Interactive flow: bulk-set custom field values from a CSV."""
    rows = cli.pick_input()

    print("Fetching people and field definitions…")
    people = get_all_people(pco)
    field_defs = get_field_definitions(pco)

    updates, problems = plan_updates(rows, people, field_defs)
    for p in sorted(set(problems)):
        print(f"  {p}")

    preview = [f"→ {u['person_name']}: {u['field_name']} = {u['value']!r}" for u in updates]
    if not confirm_apply(preview, "field updates"):
        print("Aborted — nothing was changed.")
        return

    applied = errors = 0
    for u in updates:
        try:
            existing = get_person_field_data(pco, u["person_id"])
            existing_id = next(
                (
                    fd["id"]
                    for fd in existing
                    if (fd.get("relationships", {}).get("field_definition", {}) or {}).get("data", {})
                    and fd["relationships"]["field_definition"]["data"]["id"] == u["field_definition_id"]
                ),
                None,
            )
            set_field_datum(pco, u["person_id"], u["field_definition_id"], u["value"], existing_id)
            print(f"  ✓ {u['person_name']}: {u['field_name']} = {u['value']}")
            applied += 1
        except Exception as e:
            print(f"  ✗ {u['person_name']} ({u['field_name']}): {e}")
            errors += 1

    print(f"\n── Summary ──\n  Applied: {applied}\n  Errors: {errors}\n  Problems: {len(problems)}")
