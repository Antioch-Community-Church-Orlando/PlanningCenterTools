"""Tests for Check-Ins report logic."""
from checkins.first_timers import collect_first_timers
from checkins.lapsed import split_attenders
from checkins.trends import build_trend_records


def _period(date, regular, guest=0, volunteer=0):
    return {
        "id": "x",
        "attributes": {
            "starts_at": f"{date}T09:00:00Z",
            "regular_count": regular,
            "guest_count": guest,
            "volunteer_count": volunteer,
        },
    }


def _check_in(person_id, name, created):
    return {
        "data": {
            "id": f"ci-{person_id}-{created}",
            "type": "CheckIn",
            "attributes": {"created_at": created},
            "relationships": {"person": {"data": {"id": person_id, "type": "Person"}}},
        },
        "included": [{"id": person_id, "type": "Person", "attributes": {"name": name}}],
    }


def test_trend_records_totals_and_rolling_avg():
    rows = build_trend_records(
        [
            _period("2024-06-02", 100, 10, 20),
            _period("2024-06-09", 80, 10, 10),
        ]
    )
    assert rows[0]["total"] == 130
    assert rows[1]["total"] == 100
    assert rows[1]["rolling_avg_total"] == 115.0


def test_trend_records_sorted_by_date():
    rows = build_trend_records([_period("2024-06-09", 1), _period("2024-06-02", 2)])
    assert [r["date"] for r in rows] == ["2024-06-02", "2024-06-09"]


def test_first_timers_stops_at_cutoff():
    records = iter(
        [
            _check_in("p1", "New Visitor", "2024-06-09T09:00:00Z"),
            _check_in("p2", "Old Visitor", "2024-01-01T09:00:00Z"),
        ]
    )
    rows = collect_first_timers(records, "2024-06-01T00:00:00Z")
    assert [r["person_name"] for r in rows] == ["New Visitor"]


def test_lapsed_flags_absent_regulars():
    # Newest-first: p1 seen recently, p2 last seen long ago.
    records = iter(
        [
            _check_in("p1", "Faithful", "2024-06-09T09:00:00Z"),
            _check_in("p2", "Lapsed", "2024-03-01T09:00:00Z"),
            _check_in("p1", "Faithful", "2024-02-01T09:00:00Z"),
        ]
    )
    lapsed = split_attenders(records, "2024-05-01T00:00:00Z", "2024-01-01T00:00:00Z")
    assert [r["person_name"] for r in lapsed] == ["Lapsed"]
    assert lapsed[0]["last_checked_in"] == "2024-03-01"


def test_lapsed_ignores_one_time_guests():
    rec = _check_in("p1", "Guest", "2024-03-01T09:00:00Z")
    rec["data"]["relationships"]["person"]["data"] = None
    lapsed = split_attenders(iter([rec]), "2024-05-01T00:00:00Z", "2024-01-01T00:00:00Z")
    assert lapsed == []
