"""Reconcile names in SummerMissionsDates2026.csv against the canonical spellings in people.csv.

For each name in SummerMissions:
  - Exact match (case-insensitive): no change needed.
  - Close match found: prompt to confirm the spelling correction.
  - No match: prompt to enter the correct name or remove the row.

Overwrites input/SummerMissionsDates2026.csv with confirmed corrections.
"""

import csv
import difflib
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_SUMMER_CSV = _ROOT / "input" / "SummerMissionsDates2026.csv"
_PEOPLE_CSV = _ROOT / "output" / "people.csv"


def _load_people(path: Path) -> list[tuple[str, str]]:
    """Return list of (first_name, last_name) from people.csv (lowercased)."""
    with open(path, newline="", encoding="utf-8") as f:
        return [(row["first_name"].strip(), row["last_name"].strip()) for row in csv.DictReader(f)]


def _load_summer(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _canonical_key(first: str, last: str) -> str:
    return f"{first.strip().lower()} {last.strip().lower()}"


def _find_close(first: str, last: str, people: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Return up to 3 close matches from people by full-name fuzzy similarity."""
    query = _canonical_key(first, last)
    all_keys = [_canonical_key(p[0], p[1]) for p in people]
    close_keys = difflib.get_close_matches(query, all_keys, n=3, cutoff=0.6)
    return [people[all_keys.index(k)] for k in close_keys]


def _prompt_close_match(original_first: str, original_last: str, candidates: list[tuple[str, str]]) -> tuple[str, str] | None:
    """Prompt user to accept a close match or enter a custom name. Returns corrected (first, last) or None to remove."""
    print(f'\n  No exact match for "{original_first} {original_last}"')
    print("  Close matches found:")
    for i, (f, l) in enumerate(candidates, 1):
        print(f"    {i}. {f} {l}")
    print("  Or enter a custom name / 'remove' to delete this row / 'skip' to keep as-is")

    while True:
        choice = input("  Your choice: ").strip()
        if choice.lower() == "remove":
            return None
        if choice.lower() == "skip":
            return (original_first, original_last)
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(candidates):
                return candidates[idx]
            print("  Invalid number, try again.")
        elif choice:
            parts = choice.split(None, 1)
            if len(parts) == 2:
                return (parts[0], parts[1])
            print("  Please enter both first and last name (e.g. 'John Smith').")


def _prompt_no_match(original_first: str, original_last: str) -> tuple[str, str] | None:
    """Prompt user when no fuzzy match is found. Returns corrected (first, last) or None to remove."""
    print(f'\n  "{original_first} {original_last}" was not found in people.csv and has no close matches.')
    print("  Enter the correct name, 'remove' to delete this row, or 'skip' to keep as-is:")

    while True:
        choice = input("  Your choice: ").strip()
        if choice.lower() == "remove":
            return None
        if choice.lower() == "skip":
            return (original_first, original_last)
        parts = choice.split(None, 1)
        if len(parts) == 2:
            return (parts[0], parts[1])
        print("  Please enter both first and last name (e.g. 'John Smith').")


def reconcile():
    people = _load_people(_PEOPLE_CSV)
    rows = _load_summer(_SUMMER_CSV)
    fieldnames = list(rows[0].keys()) if rows else []

    people_exact: set[str] = {_canonical_key(f, l) for f, l in people}

    updated_rows: list[dict] = []
    changes: list[str] = []

    for row in rows:
        original_first = row["First Name"].strip()
        original_last = row["Last Name"].strip()
        key = _canonical_key(original_first, original_last)

        if key in people_exact:
            # Exact match — still normalise capitalisation to people.csv spelling
            matched = next((p for p in people if _canonical_key(p[0], p[1]) == key), None)
            if matched and (matched[0] != original_first or matched[1] != original_last):
                # Skip "fix" if people.csv has all-lowercase (data quality issue there)
                if matched[0] == matched[0].lower() and matched[1] == matched[1].lower():
                    updated_rows.append(row)
                    continue
                print(f'  Fixing capitalisation: "{original_first} {original_last}" → "{matched[0]} {matched[1]}"')
                changes.append(f'  "{original_first} {original_last}" → "{matched[0]} {matched[1]}"')
                row = dict(row)
                row["First Name"] = matched[0]
                row["Last Name"] = matched[1]
            updated_rows.append(row)
            continue

        # No exact match — try fuzzy
        candidates = _find_close(original_first, original_last, people)
        if candidates:
            result = _prompt_close_match(original_first, original_last, candidates)
        else:
            result = _prompt_no_match(original_first, original_last)

        if result is None:
            changes.append(f'  REMOVED "{original_first} {original_last}"')
            continue

        new_first, new_last = result
        if new_first != original_first or new_last != original_last:
            changes.append(f'  "{original_first} {original_last}" → "{new_first} {new_last}"')
        row = dict(row)
        row["First Name"] = new_first
        row["Last Name"] = new_last
        updated_rows.append(row)

    # Write back
    with open(_SUMMER_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(updated_rows)

    print(f"\n✓ Done. {_SUMMER_CSV} updated.")
    if changes:
        print(f"  {len(changes)} change(s) made:")
        for c in changes:
            print(c)
    else:
        print("  No changes were needed.")


if __name__ == "__main__":
    reconcile()
