"""Extract all people from Planning Center People and export to JSON + CSV."""

import csv
import json
from pathlib import Path

import pypco

from pco.client import _iterate_to_list

_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"


def extract_people(pco: pypco.PCO):
    """Fetch every person from the People API and write to output/.

    Produces:
        - output/people.json  — full API response data
        - output/people.csv   — id, first_name, last_name, login_identifier
    """
    print("Fetching all people…")
    people_data = _iterate_to_list(pco, "/people/v2/people")

    _OUTPUT_DIR.mkdir(exist_ok=True)

    with open(_OUTPUT_DIR / "people.json", "w") as f:
        json.dump(people_data, f, indent=4)
    print(f"Saved {len(people_data)} people to output/people.json")

    rows = []
    for person in people_data:
        rows.append({
            "id": person["id"],
            "first_name": person["attributes"]["first_name"],
            "last_name": person["attributes"]["last_name"],
            "login_identifier": person["attributes"].get("login_identifier", ""),
        })

    with open(_OUTPUT_DIR / "people.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "first_name", "last_name", "login_identifier"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved {len(rows)} people to output/people.csv")
