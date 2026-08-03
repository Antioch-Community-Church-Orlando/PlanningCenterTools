"""Background-check compliance report.

Cross-references Services volunteers with the People API's
``passed_background_check`` flag — anyone actively serving without a passed
background check is flagged. Critical for child-ministry compliance.
"""
from __future__ import annotations

import pypco

from pco import report
from pco.client import get_all_services_people
from pco.people_api import get_all_people


def build_compliance_records(
    services_people: list[dict], people_records: list[dict]
) -> list[dict]:
    """Flag Services volunteers whose People profile lacks a passed check."""
    checks: dict[str, dict] = {}
    for person in people_records:
        attrs = person["attributes"]
        name = attrs.get("name") or f"{attrs.get('first_name', '')} {attrs.get('last_name', '')}".strip()
        checks[name.lower()] = {
            "passed": bool(attrs.get("passed_background_check")),
            "status": attrs.get("status", ""),
        }

    records = []
    for sp in services_people:
        attrs = sp["attributes"]
        full_name = attrs.get("full_name", "")
        check = checks.get(full_name.lower())
        if check is None:
            records.append(
                {
                    "person_name": full_name,
                    "services_person_id": sp["id"],
                    "issue": "no matching People profile found",
                }
            )
        elif not check["passed"]:
            records.append(
                {
                    "person_name": full_name,
                    "services_person_id": sp["id"],
                    "issue": "no passed background check on file",
                }
            )
    return records


def background_check_report(pco: pypco.PCO) -> None:
    """Report Services volunteers without a passed background check."""
    print("Fetching Services people…")
    services_people = get_all_services_people(pco)
    print("Fetching People profiles…")
    people_records = get_all_people(pco)

    records = build_compliance_records(services_people, people_records)

    print(f"\nChecked {len(services_people)} Services volunteers.")
    if not records:
        print("✓ Everyone serving has a passed background check.")
    for r in records:
        print(f"  ✗ {r['person_name']}: {r['issue']}")

    out = report.write(
        "background_checks",
        records,
        fields=["person_name", "services_person_id", "issue"],
        summary_lines=[
            f"Services volunteers checked: {len(services_people)}",
            f"Flagged: {len(records)}",
        ]
        + [f"- {r['person_name']}: {r['issue']}" for r in records],
        scope="Services volunteers vs People background checks",
    )
    print(f"✓ Report written to {out}/background_checks.*")
