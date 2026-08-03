"""Duplicate person detection.

Pulls the full People database and flags probable duplicate profiles for
human review. Merging is NOT possible via the PCO API (confirmed by PCO:
https://github.com/planningcenter/developers/issues/561) — merge candidates
in the Planning Center UI (People → duplicate merge tool).
"""
from __future__ import annotations

from difflib import SequenceMatcher

import pypco

from pco import report
from pco.people_api import get_people_with_emails

_NAME_SIMILARITY = 0.92


def _emails(record: dict) -> set[str]:
    return {
        inc["attributes"]["address"].strip().lower()
        for inc in record.get("included", [])
        if inc.get("type") == "Email" and inc["attributes"].get("address")
    }


def _norm_name(attrs: dict) -> str:
    first = (attrs.get("first_name") or "").strip().lower()
    last = (attrs.get("last_name") or "").strip().lower()
    return f"{first} {last}".strip()


def detect_duplicates(records: list[dict]) -> list[dict]:
    """Flag probable duplicate people.

    Signals (any one flags a pair):
      - identical email address on two profiles
      - identical normalized first+last name
      - same last name + same birthdate
      - full-name similarity ≥ 0.92 with same last-name initial

    Args:
        records: ``{"data": person, "included": [Email, ...]}`` dicts.

    Returns:
        One record per flagged pair with the reason.
    """
    people = []
    for rec in records:
        data = rec["data"]
        attrs = data["attributes"]
        people.append(
            {
                "id": data["id"],
                "name": _norm_name(attrs),
                "display": attrs.get("name") or _norm_name(attrs).title(),
                "last": (attrs.get("last_name") or "").strip().lower(),
                "birthdate": attrs.get("birthdate") or "",
                "emails": _emails(rec),
                "status": attrs.get("status", ""),
            }
        )

    results: list[dict] = []
    seen_pairs: set[tuple[str, str]] = set()

    def flag(a: dict, b: dict, reason: str) -> None:
        key = tuple(sorted((a["id"], b["id"])))
        if key in seen_pairs:
            return
        seen_pairs.add(key)
        results.append(
            {
                "person_a": a["display"],
                "person_a_id": a["id"],
                "person_b": b["display"],
                "person_b_id": b["id"],
                "reason": reason,
                "statuses": f"{a['status']}/{b['status']}",
            }
        )

    by_email: dict[str, dict] = {}
    by_name: dict[str, dict] = {}
    by_last_birth: dict[tuple[str, str], dict] = {}

    for p in people:
        for email in p["emails"]:
            if email in by_email:
                flag(by_email[email], p, f"same email: {email}")
            else:
                by_email[email] = p

        if p["name"]:
            if p["name"] in by_name:
                flag(by_name[p["name"]], p, f"identical name: {p['display']}")
            else:
                by_name[p["name"]] = p

        if p["last"] and p["birthdate"]:
            key = (p["last"], p["birthdate"])
            if key in by_last_birth:
                flag(by_last_birth[key], p, f"same last name + birthdate ({p['birthdate']})")
            else:
                by_last_birth[key] = p

    # Fuzzy pass, bucketed by last-name initial to stay O(n·bucket).
    buckets: dict[str, list[dict]] = {}
    for p in people:
        if p["name"] and p["last"]:
            buckets.setdefault(p["last"][0], []).append(p)
    for bucket in buckets.values():
        for i, a in enumerate(bucket):
            for b in bucket[i + 1 :]:
                if a["name"] == b["name"]:
                    continue  # already handled exactly
                if SequenceMatcher(None, a["name"], b["name"]).ratio() >= _NAME_SIMILARITY:
                    flag(a, b, f"similar names: {a['display']} ≈ {b['display']}")

    return results


def find_duplicate_people(pco: pypco.PCO) -> None:
    """Scan the entire People database for probable duplicates."""
    print("Fetching all people (with emails)…")
    records = get_people_with_emails(pco)
    results = detect_duplicates(records)

    print(f"\nScanned {len(records)} people.")
    if not results:
        print("✓ No probable duplicates found.")
    for r in results:
        print(f"  ⚠  {r['person_a']} ↔ {r['person_b']} — {r['reason']}")

    out = report.write(
        "duplicate_people",
        results,
        fields=["person_a", "person_a_id", "person_b", "person_b_id", "reason", "statuses"],
        summary_lines=[
            f"People scanned: {len(records)}",
            f"Probable duplicate pairs: {len(results)}",
            "",
            "Merging is only possible in the Planning Center UI"
            " (People → person profile → Merge).",
        ],
        scope="People database",
    )
    print(f"✓ Review list written to {out}/duplicate_people.*")
    print("  Note: merging must be done in the Planning Center UI — the API cannot merge.")
