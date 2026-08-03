"""Tests for pco/models.py from_api constructors and properties."""
from datetime import UTC, datetime

from pco.models import (
    Blockout,
    NeededPosition,
    Person,
    Plan,
    PlanPerson,
    TeamPositionAssignment,
    normalize_status,
)
from tests.fixtures import (
    BLOCKOUT_DATA,
    NEEDED_POSITION_DATA,
    PERSON_DATA,
    PLAN_DATA,
    PLAN_PERSON_DATA,
    PLAN_PERSON_DECLINED,
    PLAN_PERSON_NULL_PERSON,
    PTPA_DATA,
)


def test_plan_from_api_basic():
    plan = Plan.from_api(PLAN_DATA, service_type_id="st1", service_type_name="Main")
    assert plan.id == "1234"
    assert plan.name == "Weekend Service"
    assert plan.sort_date == datetime(2024, 6, 1, 17, 0, 0, tzinfo=UTC)
    assert plan.dates == "June 1, 2024"
    assert plan.service_type_id == "st1"
    assert plan.service_type_name == "Main"


def test_plan_falls_back_to_series_title():
    data = {"id": "2", "attributes": {"title": None, "series_title": "Advent", "sort_date": "2024-12-01T00:00:00Z"}}
    assert Plan.from_api(data).name == "Advent"


def test_person_from_api():
    person = Person.from_api(PERSON_DATA)
    assert person.id == "5678"
    assert person.full_name == "John Doe"
    assert person.sort_key == "john doe"


def test_plan_person_confirmed():
    pp = PlanPerson.from_api(PLAN_PERSON_DATA, team_map={"3456": "Sound Team"}, plan_id="1234")
    assert pp.id == "9012"
    assert pp.person_id == "5678"
    assert pp.person_name == "John Doe"
    assert pp.status == "C"
    assert pp.is_confirmed and not pp.is_declined and not pp.is_unconfirmed
    assert pp.team_id == "3456"
    assert pp.team_name == "Sound Team"
    assert pp.position == "Sound"
    assert pp.plan_id == "1234"
    assert pp.notification_sent_at == datetime(2024, 5, 18, 12, 0, tzinfo=UTC)
    assert pp.notification_read_at == datetime(2024, 5, 19, 8, 0, tzinfo=UTC)


def test_plan_person_declined():
    pp = PlanPerson.from_api(PLAN_PERSON_DECLINED)
    assert pp.is_declined
    assert pp.decline_reason == "Out of town"
    assert pp.status_updated_at == datetime(2024, 5, 21, 9, 0, tzinfo=UTC)
    assert pp.notification_read_at is None


def test_plan_person_null_person_relationship():
    """Empty to-one relationships come back as "data": null — must not crash."""
    pp = PlanPerson.from_api(PLAN_PERSON_NULL_PERSON)
    assert pp.person_id == ""
    assert pp.is_unconfirmed


def test_normalize_status_long_forms():
    assert normalize_status("Confirmed") == "C"
    assert normalize_status("Unconfirmed") == "U"
    assert normalize_status("Declined") == "D"
    assert normalize_status("C") == "C"


def test_blockout_from_api_and_contains():
    bo = Blockout.from_api(BLOCKOUT_DATA, person_id="5678")
    assert bo.person_id == "5678"
    assert bo.reason == "Vacation"
    assert bo.contains(datetime(2024, 7, 7, 12, 0, tzinfo=UTC))
    assert bo.contains(datetime(2024, 7, 1, 0, 0, tzinfo=UTC))
    assert bo.contains(datetime(2024, 7, 14, 0, 0, tzinfo=UTC))
    assert not bo.contains(datetime(2024, 6, 30, 23, 59, tzinfo=UTC))
    assert not bo.contains(datetime(2024, 7, 15, 0, 0, tzinfo=UTC))


def test_needed_position_quantity_is_open_count():
    np = NeededPosition.from_api(NEEDED_POSITION_DATA, plan_id="1234", team_name="Worship")
    assert np.id == "1122"
    assert np.team_id == "3456"
    assert np.team_name == "Worship"
    assert np.position_name == "Worship Leader"
    assert np.quantity == 2
    assert not hasattr(np, "accepted_count")  # attribute doesn't exist in the API


def test_ptpa_from_api():
    a = TeamPositionAssignment.from_api(PTPA_DATA)
    assert a.person_id == "5678"
    assert a.team_position_id == "6677"
    assert a.schedule_preference == "Every other week"
