"""Forms submissions export: aggregate submissions across all forms."""
from __future__ import annotations

import pypco

from pco import report
from pco.people_api import get_form_submissions, get_forms


def export_form_submissions(pco: pypco.PCO) -> None:
    """Export every form's submissions to output/form_submissions.*"""
    forms = get_forms(pco)
    if not forms:
        print("✗ No forms found in People.")
        return

    records = []
    for form in forms:
        form_name = form["attributes"]["name"]
        for rec in get_form_submissions(pco, form["id"]):
            submission = rec["data"]
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
                    "form": form_name,
                    "person_name": person_name,
                    "submitted_at": submission["attributes"].get("created_at", ""),
                    "submission_id": submission["id"],
                }
            )

    records.sort(key=lambda r: r["submitted_at"], reverse=True)
    print(f"\nExported {len(records)} submissions across {len(forms)} forms.")

    out = report.write(
        "form_submissions",
        records,
        fields=["form", "person_name", "submitted_at", "submission_id"],
        summary_lines=[f"Forms: {len(forms)}", f"Total submissions: {len(records)}"],
        scope="All People forms",
    )
    print(f"✓ Export written to {out}/form_submissions.*")
