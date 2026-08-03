"""Helpers for the Planning Center Check-Ins API (/check-ins/v2).

The Check-Ins API is read-only for attendance records.
Docs: https://api.planningcenteronline.com/docs/apps/check-ins/versions/2025-05-28
"""
from __future__ import annotations

from collections.abc import Iterator

import pypco

from pco.client import _iterate_to_list


def get_events(pco: pypco.PCO) -> list[dict]:
    """GET /check-ins/v2/events"""
    return _iterate_to_list(pco, "/check-ins/v2/events")


def pick_event(pco: pypco.PCO) -> dict:
    """Interactively prompt the user to select a Check-Ins event."""
    events = get_events(pco)
    print("Choose an event:")
    for i, ev in enumerate(events, 1):
        print(f"  {i}. {ev['attributes']['name']}")
    try:
        return events[int(input("Enter the number of your choice: ")) - 1]
    except (IndexError, ValueError):
        print("Invalid choice. Please enter a number from the list.")
        return pick_event(pco)


def get_event_periods(pco: pypco.PCO, event_id: str) -> list[dict]:
    """GET /check-ins/v2/events/{id}/event_periods — per-gathering attendance counts.

    EventPeriod attributes: starts_at, ends_at, regular_count, guest_count,
    volunteer_count.
    """
    return _iterate_to_list(
        pco, f"/check-ins/v2/events/{event_id}/event_periods", order="starts_at"
    )


def iter_event_check_ins(
    pco: pypco.PCO, event_id: str, filter: str | None = None
) -> Iterator[dict]:
    """Yield check-in records for an event, newest first, with person included.

    Args:
        filter: Named scope — regular, guest, volunteer, attendee, first_time,
            one_time_guest, not_one_time_guest, checked_out.

    Yields ``{"data": check_in, "included": [Person, ...]}`` records so callers
    can stop early once they've paged past their date range.
    """
    params = {"order": "-created_at", "include": "person"}
    if filter:
        params["filter"] = filter
    yield from pco.iterate(f"/check-ins/v2/events/{event_id}/check_ins", per_page=100, **params)
