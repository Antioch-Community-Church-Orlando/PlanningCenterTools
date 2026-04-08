"""Add blockout dates in Planning Center Services for a list of people."""

import logging

import pypco
from dateutil import parser as dateutil_parser

from pco.cli import pick_input
from pco.client import get_all_services_people, get_person_blockouts

logger = logging.getLogger(__name__)

# Values treated as non-dates (case-insensitive)
_INVALID_DATE_TOKENS = {"pending", "tbd", "n/a", "na", ""}


def _parse_date(value: str) -> str | None:
    """Parse a date string into ISO 8601 format for the PCO API.

    Handles common formats: MM/DD/YYYY, YYYY-MM-DD, M/D/YYYY, MM-DD-YYYY,
    Month DD YYYY, etc.  Returns None for non-date values like "Pending".
    """
    cleaned = value.strip()
    if cleaned.lower() in _INVALID_DATE_TOKENS:
        return None
    try:
        dt = dateutil_parser.parse(cleaned, dayfirst=False)
        return dt.strftime("%Y-%m-%dT00:00:00Z")
    except (ValueError, OverflowError):
        return None


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


def _has_existing_blockout(pco: pypco.PCO, person_id: str, starts_at: str, ends_at: str) -> bool:
    """Check if the person already has a blockout with the exact same date range."""
    existing = get_person_blockouts(pco, person_id)
    for blockout in existing:
        attrs = blockout["attributes"]
        if attrs["starts_at"] == starts_at and attrs["ends_at"] == ends_at:
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


def _pick_mode() -> bool:
    """Prompt the user to choose dry-run or apply mode.

    Returns:
        True for dry run, False for apply.
    """
    print("\nMode:")
    print("  1. Dry run (preview only)")
    print("  2. Apply blockouts")
    choice = input("Enter your choice: ").strip()
    if choice == "1":
        return True
    if choice == "2":
        return False
    print("Invalid choice. Please enter 1 or 2.")
    return _pick_mode()


def add_blockouts(pco: pypco.PCO):
    """Interactive flow: pick an input CSV, then post blockout dates.

    Reads a CSV with columns: Last Name, First Name, Reason, Start Date, End Date.
    For each person, attempts to match them against Services people and creates
    the corresponding blockout (or previews in dry-run mode).
    """
    rows = pick_input()
    dry_run = _pick_mode()
    all_people = get_all_services_people(pco)

    if dry_run:
        print("\n── DRY RUN (no changes will be made) ──\n")
    else:
        print()

    stats = {"processed": 0, "skipped_date": 0, "skipped_not_found": 0, "skipped_duplicate": 0, "created": 0}

    for row in rows:
        first_name = row.get("First Name", "").strip()
        last_name = row.get("Last Name", "").strip()
        reason = row.get("Reason", "").strip()
        raw_start = row.get("Start Date", "").strip()
        raw_end = row.get("End Date", "").strip()
        full_name = f"{first_name} {last_name}".strip()

        if not full_name:
            continue

        starts_at = _parse_date(raw_start)
        ends_at = _parse_date(raw_end)

        if not starts_at or not ends_at:
            logger.warning("Skipping %s — invalid dates: Start=%r, End=%r", full_name, raw_start, raw_end)
            print(f"⚠  Skipping {full_name} — invalid or pending dates (Start={raw_start!r}, End={raw_end!r})")
            stats["skipped_date"] += 1
            continue

        stats["processed"] += 1
        print(f"Processing {full_name} ({reason})…")

        matched = False
        for person in all_people:
            if _match_person(first_name, last_name, full_name, person):
                matched = True
                if dry_run:
                    print(f"  → Would create blockout: {starts_at} to {ends_at} — {reason}")
                else:
                    if _has_existing_blockout(pco, person["id"], starts_at, ends_at):
                        logger.warning("Duplicate blockout for %s (%s to %s) — skipping", full_name, starts_at, ends_at)
                        print(f"  ⚠ Blockout already exists for {full_name} ({starts_at} to {ends_at}) — skipping")
                        stats["skipped_duplicate"] += 1
                    else:
                        _post_blockout(pco, person["id"], starts_at, ends_at, reason or "Blockout")
                        stats["created"] += 1
                break

        if not matched:
            logger.warning("No match found in Planning Center for %s", full_name)
            print(f"  ⚠ No match found for {full_name} — skipping")
            stats["skipped_not_found"] += 1

    # Summary
    print("\n── Summary ──")
    print(f"  Processed:          {stats['processed']}")
    if dry_run:
        print(f"  Would create:       {stats['processed'] - stats['skipped_not_found']}")
    else:
        print(f"  Created:            {stats['created']}")
        print(f"  Skipped (duplicate):{stats['skipped_duplicate']}")
    print(f"  Skipped (bad dates):{stats['skipped_date']}")
    print(f"  Skipped (not found):{stats['skipped_not_found']}")
