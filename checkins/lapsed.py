"""Lapsed-attender detection from Check-Ins history.

Compares who attended in a prior window against who attended recently; people
present before but absent since the cutoff are flagged for follow-up.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pypco

from pco import report
from pco.checkins_api import iter_event_check_ins, pick_event
from pco.config import get_config


def split_attenders(records, recent_cutoff_iso: str, oldest_iso: str) -> list[dict]:
    """Walk newest-first check-ins and find people absent since the cutoff.

    Returns lapsed attenders: last check-in between oldest_iso and
    recent_cutoff_iso, none after.
    """
    last_seen: dict[str, dict] = {}
    for rec in records:
        check_in = rec["data"]
        created = check_in["attributes"].get("created_at") or ""
        if created and created < oldest_iso:
            break
        person_id = (
            (check_in.get("relationships", {}).get("person", {}) or {}).get("data") or {}
        ).get("id")
        if not person_id:
            continue  # one-time guests without a person record
        if person_id in last_seen:
            continue  # newest-first: first sighting is the latest check-in
        person_name = next(
            (
                inc["attributes"].get("name", "")
                for inc in rec.get("included", [])
                if inc.get("type") == "Person"
            ),
            "",
        )
        last_seen[person_id] = {
            "person_id": person_id,
            "person_name": person_name,
            "last_checked_in": created[:10],
        }

    lapsed = [rec for rec in last_seen.values() if rec["last_checked_in"] < recent_cutoff_iso[:10]]
    lapsed.sort(key=lambda r: r["last_checked_in"])
    return lapsed


def lapsed_attenders(pco: pypco.PCO) -> None:
    """Report regular attenders who haven't checked in recently."""
    cfg = get_config()
    event = pick_event(pco)
    default_days = cfg.thresholds.inactive_threshold_days
    raw = input(f"Flag people absent for how many days? [{default_days}]: ").strip()
    absent_days = int(raw) if raw.isdigit() else default_days

    now = datetime.now(UTC)
    recent_cutoff = (now - timedelta(days=absent_days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    oldest = (now - timedelta(days=absent_days * 3)).strftime("%Y-%m-%dT%H:%M:%SZ")

    print("Fetching check-in history…")
    lapsed = split_attenders(
        iter_event_check_ins(pco, event["id"], filter="regular"), recent_cutoff, oldest
    )

    event_name = event["attributes"]["name"]
    print(f"\nAttenders of {event_name!r} absent {absent_days}+ days: {len(lapsed)}")
    for r in lapsed:
        print(f"  ⚠  {r['person_name']} — last checked in {r['last_checked_in']}")

    out = report.write(
        "lapsed_attenders",
        lapsed,
        fields=["person_name", "last_checked_in", "person_id"],
        summary_lines=[
            f"Event: {event_name}",
            f"Lapsed attenders ({absent_days}+ days absent): {len(lapsed)}",
            f"(History window: {absent_days * 3} days)",
        ],
        scope=event_name,
    )
    print(f"✓ Follow-up list written to {out}/lapsed_attenders.*")
