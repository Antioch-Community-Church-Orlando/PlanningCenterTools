"""Export plan templates and their team members from Planning Center Services."""

import csv
import json
from pathlib import Path

import pypco

from pco.client import pick_service_type, _iterate_to_list

_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"


def _pick_template(templates: list[dict]) -> dict:
    """Prompt the user to select a plan template."""
    print("Choose a template:")
    for i, t in enumerate(templates, 1):
        print(f"  {i}. {t['attributes']['name']}")

    choice = int(input("Enter the number of your choice: "))
    try:
        return templates[choice - 1]
    except (IndexError, ValueError):
        print("Invalid choice. Please try again.")
        return _pick_template(templates)


def export_templates(pco: pypco.PCO):
    """Export all plan templates for a service type to JSON, and optionally drill into one.

    Saves templates to output/plan_templates.json. If the user selects a
    specific template, its team members are also exported to
    output/template_members.json and output/template_members.csv.
    """
    service_type = pick_service_type(pco)
    st_id = service_type["id"]

    # Fetch all templates
    templates = _iterate_to_list(pco, f"/services/v2/service_types/{st_id}/plan_templates/")

    if not templates:
        print("No templates found for this service type.")
        return

    _OUTPUT_DIR.mkdir(exist_ok=True)

    with open(_OUTPUT_DIR / "plan_templates.json", "w") as f:
        json.dump(templates, f, indent=4)
    print(f"Saved {len(templates)} template(s) to output/plan_templates.json")

    template = _pick_template(templates)

    # Fetch team members for the selected template
    members_resp = pco.get(
        f"/services/v2/service_types/{st_id}/plan_templates/{template['id']}/team_members"
    )
    members = members_resp.get("data", [])

    with open(_OUTPUT_DIR / "template_members.json", "w") as f:
        json.dump(members, f, indent=4)

    # Write a human-friendly CSV
    if members:
        fieldnames = ["id", "name", "team_position_name", "status"]
        with open(_OUTPUT_DIR / "template_members.csv", "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for m in members:
                writer.writerow({
                    "id": m["id"],
                    "name": m["attributes"].get("name", ""),
                    "team_position_name": m["attributes"].get("team_position_name", ""),
                    "status": m["attributes"].get("status", ""),
                })
        print(f"Saved {len(members)} member(s) to output/template_members.csv")
    else:
        print("No team members found for this template.")
