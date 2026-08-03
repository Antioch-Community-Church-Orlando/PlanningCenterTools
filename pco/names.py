"""Fuzzy person-name matching against Services people records."""
from __future__ import annotations


def match_person(name_first: str, name_last: str, full_name: str, services_person: dict) -> bool:
    """Check whether a Services person resource matches the given name fields.

    Tries full-name equality, first+last equality, then first/last token
    comparison (handles middle names and suffixes).
    """
    attrs = services_person["attributes"]
    svc_full = (attrs.get("full_name") or "").lower()
    svc_first = (attrs.get("first_name") or "").lower()
    svc_last = (attrs.get("last_name") or "").lower()

    first = name_first.lower()
    last = name_last.lower()
    full = full_name.lower()

    if full and full == svc_full:
        return True
    if first and last and first == svc_first and last == svc_last:
        return True
    svc_tokens = svc_full.split()
    if len(svc_tokens) >= 2 and first == svc_tokens[0] and last == svc_tokens[-1]:
        return True

    return False


def find_person(full_name: str, people: list[dict]) -> dict | None:
    """Return the first Services person matching *full_name*, or None."""
    tokens = full_name.split()
    if not tokens:
        return None
    first, last = tokens[0], tokens[-1]
    for person in people:
        if match_person(first, last, full_name, person):
            return person
    return None
