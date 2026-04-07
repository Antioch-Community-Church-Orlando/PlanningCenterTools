"""Export plan templates and their team members from Planning Center Services."""

import csv
import json
import re
from itertools import zip_longest
from pathlib import Path

import pypco

from pco.client import pick_service_type, _iterate_to_list, get_template_members

_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"


def _sanitize_filename(name: str) -> str:
    """Replace characters unsafe for filenames with underscores."""
    return re.sub(r'[<>:"/\\|?*]', "_", name).strip()


def _pick_templates_multi(templates: list[dict]) -> list[dict]:
    """Prompt the user to select multiple templates for combined export.

    Enter comma-separated numbers to select, or press enter to skip grouping.
    Returns a list of selected template dicts (empty if skipped).
    """
    print("\nSelect templates to combine into a grouped CSV (with rotation column),")
    print("or press enter to skip grouping:")
    for i, t in enumerate(templates, 1):
        print(f"  {i}. {t['attributes']['name']}")

    raw = input("Enter numbers (e.g. 1,3,4) or press enter to skip: ").strip()
    if not raw:
        return []

    selected: list[dict] = []
    for token in raw.split(","):
        token = token.strip()
        try:
            idx = int(token) - 1
            if 0 <= idx < len(templates):
                selected.append(templates[idx])
            else:
                print(f"  ⚠ Skipping invalid number: {token}")
        except ValueError:
            print(f"  ⚠ Skipping non-number: {token}")

    return selected


def _resolve_team(member: dict, team_map: dict[str, str]) -> str:
    """Get the team name for a member from the team_map."""
    team_id = member.get("relationships", {}).get("team", {}).get("data", {}).get("id")
    return team_map.get(team_id, "Unknown") if team_id else "Unknown"


def _write_columnar_csv(
    members: list[dict], team_map: dict[str, str], path: Path
) -> None:
    """Write a CSV with team names as column headers and members underneath.

    Each column contains the member names for that team. Columns are ragged
    (shorter teams are padded with empty strings).
    """
    teams: dict[str, list[str]] = {}
    for m in members:
        team = _resolve_team(m, team_map)
        name = m["attributes"].get("name", "")
        teams.setdefault(team, []).append(name)

    if not teams:
        return

    headers = list(teams.keys())
    columns = [teams[h] for h in headers]

    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for row in zip_longest(*columns, fillvalue=""):
            writer.writerow(row)


def _write_flat_csv(
    members: list[dict],
    team_map: dict[str, str],
    path: Path,
    rotation: str | None = None,
) -> None:
    """Write a flat CSV with id, name, team, position (and optional rotation).

    Args:
        members: List of team-member resource dicts.
        team_map: Mapping of team IDs to team names.
        path: Output file path.
        rotation: If provided, added as an extra column value for every row.
    """
    fieldnames = ["id", "name", "team", "position"]
    if rotation is not None:
        fieldnames.append("rotation")

    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for m in members:
            attrs = m["attributes"]
            row = {
                "id": m["id"],
                "name": attrs.get("name", ""),
                "team": _resolve_team(m, team_map),
                "position": attrs.get("team_position_name", ""),
            }
            if rotation is not None:
                row["rotation"] = rotation
            writer.writerow(row)


def export_templates(pco: pypco.PCO) -> None:
    """Export all plan templates and their team members for a service type.

    For each template, creates:
      - output/{name}_teams.csv   — columnar layout (team headers, members below)
      - output/{name}_members.csv — flat list (id, name, team, position)

    Optionally combines selected templates into a grouped CSV with a rotation column.
    """
    service_type = pick_service_type(pco)
    st_id = service_type["id"]

    templates = _iterate_to_list(pco, f"/services/v2/service_types/{st_id}/plan_templates/")
    if not templates:
        print("No templates found for this service type.")
        return

    _OUTPUT_DIR.mkdir(exist_ok=True)

    with open(_OUTPUT_DIR / "plan_templates.json", "w") as f:
        json.dump(templates, f, indent=4)
    print(f"Saved {len(templates)} template(s) to output/plan_templates.json")

    # Fetch all members for every template
    template_members: dict[str, tuple[list[dict], dict[str, str]]] = {}
    for t in templates:
        name = t["attributes"]["name"]
        members, team_map = get_template_members(pco, st_id, t["id"])
        template_members[name] = (members, team_map)
        print(f"  Fetched {len(members)} member(s) for '{name}'")

    # Write per-template CSVs
    for name, (members, team_map) in template_members.items():
        safe = _sanitize_filename(name)
        if not members:
            print(f"  No members for '{name}', skipping CSVs.")
            continue
        _write_columnar_csv(members, team_map, _OUTPUT_DIR / f"{safe}_teams.csv")
        _write_flat_csv(members, team_map, _OUTPUT_DIR / f"{safe}_members.csv")
        print(f"  ✓ Wrote {safe}_teams.csv and {safe}_members.csv")

    # Optional grouping
    selected = _pick_templates_multi(templates)
    if selected:
        combined_path = _OUTPUT_DIR / "combined_members.csv"
        fieldnames = ["id", "name", "team", "position", "rotation"]

        rows: list[dict] = []
        for t in selected:
            name = t["attributes"]["name"]
            members, team_map = template_members.get(name, ([], {}))
            for m in members:
                attrs = m["attributes"]
                rows.append({
                    "id": m["id"],
                    "name": attrs.get("name", ""),
                    "team": _resolve_team(m, team_map),
                    "position": attrs.get("team_position_name", ""),
                    "rotation": name,
                })

        rows.sort(key=lambda r: r["name"].casefold())

        with open(combined_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        print(f"  ✓ Wrote combined_members.csv with {len(selected)} rotation(s)")
    else:
        print("  Skipped grouped export.")
