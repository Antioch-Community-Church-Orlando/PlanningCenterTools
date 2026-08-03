"""Tests for report aggregation logic (pure functions, no API)."""
from datetime import UTC, datetime

from pco.models import Blockout, PlanPerson
from services.reports.blockout_conflicts import find_conflicts
from services.reports.cross_duplicates import find_cross_duplicates
from services.reports.decline_detector import _collect
from services.reports.notifications import audit_notifications
from services.reports.volunteer_health import _max_consecutive_weeks, build_health_records


def _pp(
    person_id="p1",
    name="John Doe",
    status="C",
    plan_id="pl1",
    plan_date=datetime(2024, 6, 2, 10, 0, tzinfo=UTC),
    team_id="t1",
    team_name="Sound",
    service_type_name="Main",
    **kwargs,
) -> PlanPerson:
    return PlanPerson(
        id="x",
        person_id=person_id,
        person_name=name,
        status=status,
        team_id=team_id,
        team_name=team_name,
        position="Tech",
        plan_id=plan_id,
        plan_date=plan_date,
        service_type_id="st1",
        service_type_name=service_type_name,
        **kwargs,
    )


# ── decline detector ─────────────────────────────────────────────────────────


def test_collect_counts_by_status():
    members = [
        _pp(status="C"),
        _pp(status="D", decline_reason="sick", status_updated_at=datetime(2024, 5, 1, tzinfo=UTC)),
        _pp(status="U"),
        _pp(status="D"),
    ]
    [rec] = _collect(members)
    assert rec["requests"] == 4
    assert rec["confirmed"] == 1
    assert rec["declines"] == 2
    assert rec["pending"] == 1
    assert rec["decline_rate"] == 0.5
    assert rec["pending_rate"] == 0.25
    assert "sick" in rec["decline_reasons"]


def test_collect_skips_unassigned_slots():
    assert _collect([_pp(person_id="")]) == []


# ── volunteer health ─────────────────────────────────────────────────────────


def test_max_consecutive_weeks():
    dates = [
        datetime(2024, 6, 2, tzinfo=UTC),   # week 22
        datetime(2024, 6, 9, tzinfo=UTC),   # week 23
        datetime(2024, 6, 16, tzinfo=UTC),  # week 24
        datetime(2024, 7, 7, tzinfo=UTC),   # gap
    ]
    assert _max_consecutive_weeks(dates) == 3
    assert _max_consecutive_weeks([]) == 0


def test_health_serves_count_confirmed_only():
    """Declined assignments must NOT count as serves."""
    members = [
        _pp(status="D", plan_date=datetime(2024, 6, 2, tzinfo=UTC)),
        _pp(status="D", plan_date=datetime(2024, 6, 9, tzinfo=UTC)),
        _pp(status="C", plan_date=datetime(2024, 6, 16, tzinfo=UTC)),
    ]
    [rec] = build_health_records(members, window_days=90)
    assert rec["serves"] == 1
    assert rec["declines"] == 2
    assert rec["requests"] == 3
    assert rec["decline_rate"] == 0.67


def test_health_multi_team_same_day():
    members = [
        _pp(status="C", team_id="t1", plan_id="pl1"),
        _pp(status="C", team_id="t2", plan_id="pl2"),
    ]
    [rec] = build_health_records(members, window_days=90)
    assert rec["multi_team_days"] == 1


def test_health_all_decliner_scores_low_serve_component():
    members = [_pp(status="D") for _ in range(5)]
    [rec] = build_health_records(members, window_days=90)
    assert rec["serves"] == 0
    assert rec["serves_per_month"] == 0


# ── cross duplicates ─────────────────────────────────────────────────────────


def test_cross_duplicates_flags_two_plans_same_day():
    members = [
        _pp(plan_id="pl1", service_type_name="Main"),
        _pp(plan_id="pl2", service_type_name="Youth"),
    ]
    [rec] = find_cross_duplicates(members)
    assert rec["plan_count"] == 2
    assert "Main" in rec["assignments"] and "Youth" in rec["assignments"]


def test_cross_duplicates_ignores_same_plan_double_position():
    """Two positions in ONE plan is normal, not a cross-service duplicate."""
    members = [
        _pp(plan_id="pl1", team_id="t1"),
        _pp(plan_id="pl1", team_id="t2"),
    ]
    assert find_cross_duplicates(members) == []


def test_cross_duplicates_ignores_declined():
    members = [
        _pp(plan_id="pl1", status="D"),
        _pp(plan_id="pl2", status="C"),
    ]
    assert find_cross_duplicates(members) == []


# ── blockout conflicts ───────────────────────────────────────────────────────


def _bo(start, end, person_id="p1", reason="Vacation") -> Blockout:
    return Blockout(id="b1", person_id=person_id, starts_at=start, ends_at=end, reason=reason)


def test_conflict_detected_inside_blockout():
    member = _pp(plan_date=datetime(2024, 7, 7, 10, 0, tzinfo=UTC))
    blockouts = {"p1": [_bo(datetime(2024, 7, 1, tzinfo=UTC), datetime(2024, 7, 14, tzinfo=UTC))]}
    [rec] = find_conflicts([member], blockouts)
    assert rec["blockout_reason"] == "Vacation"
    assert rec["date"] == "2024-07-07"


def test_no_conflict_outside_blockout():
    member = _pp(plan_date=datetime(2024, 8, 1, 10, 0, tzinfo=UTC))
    blockouts = {"p1": [_bo(datetime(2024, 7, 1, tzinfo=UTC), datetime(2024, 7, 14, tzinfo=UTC))]}
    assert find_conflicts([member], blockouts) == []


def test_declined_assignment_not_a_conflict():
    member = _pp(status="D", plan_date=datetime(2024, 7, 7, tzinfo=UTC))
    blockouts = {"p1": [_bo(datetime(2024, 7, 1, tzinfo=UTC), datetime(2024, 7, 14, tzinfo=UTC))]}
    assert find_conflicts([member], blockouts) == []


# ── notification audit ───────────────────────────────────────────────────────


def test_audit_flags_never_sent_and_unread():
    members = [
        _pp(status="U", notification_sent_at=None),
        _pp(
            person_id="p2",
            name="Jane",
            status="U",
            notification_sent_at=datetime(2024, 5, 18, tzinfo=UTC),
            notification_read_at=None,
        ),
        _pp(
            person_id="p3",
            status="U",
            notification_sent_at=datetime(2024, 5, 18, tzinfo=UTC),
            notification_read_at=datetime(2024, 5, 19, tzinfo=UTC),
        ),
        _pp(person_id="p4", status="C", notification_sent_at=None),
    ]
    records = audit_notifications(members)
    issues = {r["person_id"]: r["issue"] for r in records}
    assert issues == {
        "p1": "notification never sent",
        "p2": "notification sent but unread",
    }
