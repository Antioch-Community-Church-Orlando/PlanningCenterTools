"""Add blockout dates in Planning Center Services for a list of people."""

import pypco

from pco.cli import pick_input, get_blockout_info
from pco.client import get_all_services_people


def _match_person(name_first: str, name_last: str, full_name: str, services_person: dict) -> bool:
    """Check whether a services person matches the given name fields."""
    attrs = services_person["attributes"]
    svc_full = attrs["full_name"].lower()
    svc_first = attrs.get("first_name", "").lower()
    svc_last = attrs.get("last_name", "").lower()

    first = name_first.lower()
    last = name_last.lower()
    full = full_name.lower()

    if full == svc_full:
        return True
    if first == svc_first and last == svc_last:
        return True
    # Handle nicknames / middle-name mismatches by comparing first & last tokens
    svc_tokens = svc_full.split()
    if len(svc_tokens) >= 2 and first == svc_tokens[0] and last == svc_tokens[-1]:
        return True

    return False


def _post_blockout(pco: pypco.PCO, person_id: str, starts_at: str, ends_at: str, reason: str):
    """Post a single blockout date for a person."""
    payload = pco.template(
        "BlockoutDate",
        {
            "reason": reason,
            "repeat_frequency": "no_repeat",
            "starts_at": starts_at,
            "ends_at": ends_at,
            "share": "false",
        },
    )
    try:
        result = pco.post(f"/services/v2/people/{person_id}/blockouts", payload=payload)
        desc = result["data"]["attributes"]["description"]
        print(f"  ✓ Blockout {result['data']['id']} created for {person_id} — {desc}")
    except Exception as e:
        print(f"  ✗ Error creating blockout for {person_id}: {e}")


def add_blockouts(pco: pypco.PCO):
    """Interactive flow: pick an input CSV + blockouts.json, then post blockout dates.

    For each person in the CSV, attempts to match them against Services people
    and creates the corresponding blockout.
    """
    names = pick_input()
    blockouts = get_blockout_info()
    all_people = get_all_services_people(pco)

    for row in names:
        full_name = row.get("Full Name", f"{row.get('First Name', '')} {row.get('Last Name', '')}").strip()
        first_name = row.get("First Name") or full_name.split()[0]
        last_name = row.get("Last Name") or full_name.split()[-1]

        trip = row.get("Trip", "")
        if trip not in blockouts:
            print(f"⚠  No blockout info for trip '{trip}' — skipping {full_name}")
            continue

        blockout = blockouts[trip]
        print(f"Processing {full_name} ({trip})…")

        matched = False
        for person in all_people:
            if _match_person(first_name, last_name, full_name, person):
                _post_blockout(pco, person["id"], blockout["starts_at"], blockout["ends_at"], blockout.get("reason", trip))
                matched = True
                break

        if not matched:
            print(f"  ✗ No match found for {full_name}")
