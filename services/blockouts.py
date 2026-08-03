"""Add blockout dates in Planning Center Services for a list of people."""

import logging
import os
from datetime import UTC
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pypco
from dateutil import parser as dateutil_parser

from pco.cli import pick_input
from pco.client import get_all_services_people, get_person_blockouts, post_blockout
from pco.names import match_person as _match_person

logger = logging.getLogger(__name__)

# Values treated as non-dates (case-insensitive)
_INVALID_DATE_TOKENS = {"pending", "tbd", "n/a", "na", ""}


def _parse_date(value: str, tz: ZoneInfo) -> str | None:
    """Parse a date string into ISO 8601 UTC format for the PCO API.

    Interprets the date as midnight in the given local timezone, then converts
    to UTC. Handles common formats: MM/DD/YYYY, YYYY-MM-DD, M/D/YYYY, etc.
    Returns None for non-date values like "Pending".
    """
    cleaned = value.strip()
    if cleaned.lower() in _INVALID_DATE_TOKENS:
        return None
    try:
        dt_naive = dateutil_parser.parse(cleaned, dayfirst=False)
        dt_local = dt_naive.replace(tzinfo=tz)
        dt_utc = dt_local.astimezone(UTC)
        return dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    except (ValueError, OverflowError):
        return None



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
        result = post_blockout(pco, person_id, payload)
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
    Requires PCO_TIMEZONE to be set in .env (e.g. America/New_York).
    For each person, attempts to match them against Services people and creates
    the corresponding blockout (or previews in dry-run mode).
    """
    tz_name = os.environ.get("PCO_TIMEZONE", "").strip()
    if not tz_name:
        print(
            "✗ PCO_TIMEZONE is not set.\n"
            "  Add it to your .env file — see .env.example for common timezone names.\n"
            "  Example: PCO_TIMEZONE=America/New_York"
        )
        return

    try:
        tz = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        print(
            f"✗ PCO_TIMEZONE={tz_name!r} is not a valid IANA timezone name.\n"
            "  See .env.example for common examples (e.g. America/New_York, America/Chicago)."
        )
        return

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
        raw_start = (row.get("Start Date") or "").strip()
        raw_end = (row.get("End Date") or "").strip()
        full_name = f"{first_name} {last_name}".strip()

        if not full_name:
            continue

        starts_at = _parse_date(raw_start, tz)
        ends_at = _parse_date(raw_end, tz)

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
                if _has_existing_blockout(pco, person["id"], starts_at, ends_at):
                    logger.warning("Duplicate blockout for %s (%s to %s) — skipping", full_name, starts_at, ends_at)
                    print(f"  ⚠ Blockout already exists for {full_name} ({starts_at} to {ends_at}) — skipping")
                    stats["skipped_duplicate"] += 1
                elif dry_run:
                    print(f"  → Would create blockout: {starts_at} to {ends_at} — {reason}")
                    stats["created"] += 1
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
        print(f"  Would create:       {stats['created']}")
    else:
        print(f"  Created:            {stats['created']}")
    print(f"  Skipped (duplicate):{stats['skipped_duplicate']}")
    print(f"  Skipped (bad dates):{stats['skipped_date']}")
    print(f"  Skipped (not found):{stats['skipped_not_found']}")
