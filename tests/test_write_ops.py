"""Tests for write-operation building blocks (payloads, diffs, matching)."""
from datetime import UTC, datetime

from pco.models import Plan, PlanPerson
from pco.names import find_person, match_person
from services.write.auto_blockout import find_repeated_decliners
from services.write.bulk_schedule import build_plan_person_payload, match_rows
from services.write.roster_sync import diff_roster
from services.write.template_copy import build_import_payload
from tests.fixtures import PERSON_DATA

PEOPLE = [
    PERSON_DATA,
    {
        "id": "111",
        "type": "Person",
        "attributes": {
            "first_name": "Mary",
            "last_name": "Smith",
            "full_name": "Mary Anne Smith",
        },
    },
]

PLANS = [
    Plan(
        id="pl1",
        name="Weekend",
        sort_date=datetime(2024, 6, 2, 10, 0, tzinfo=UTC),
        dates="June 2",
        service_type_id="st1",
    )
]

TEAMS = [{"id": "t1", "type": "Team", "attributes": {"name": "Sound Team"}}]


# ── name matching ────────────────────────────────────────────────────────────


def test_match_person_exact_full_name():
    assert match_person("John", "Doe", "John Doe", PERSON_DATA)


def test_match_person_middle_name_tokens():
    assert match_person("Mary", "Smith", "Mary Smith", PEOPLE[1])


def test_find_person_none_for_unknown():
    assert find_person("Nobody Here", PEOPLE) is None
    assert find_person("", PEOPLE) is None


# ── bulk schedule ────────────────────────────────────────────────────────────


def test_build_plan_person_payload():
    payload = build_plan_person_payload("5678", "t1", "Sound", notify=True)
    data = payload["data"]
    assert data["type"] == "PlanPerson"
    assert data["attributes"]["status"] == "U"
    assert data["attributes"]["team_position_name"] == "Sound"
    assert data["attributes"]["prepare_notification"] is True
    assert data["relationships"]["person"]["data"]["id"] == "5678"
    assert data["relationships"]["team"]["data"]["id"] == "t1"


def test_build_plan_person_payload_minimal():
    payload = build_plan_person_payload("5678", "t1", "", notify=False)
    attrs = payload["data"]["attributes"]
    assert "team_position_name" not in attrs
    assert "prepare_notification" not in attrs


def test_match_rows_resolves_and_reports_problems():
    rows = [
        {"Full Name": "John Doe", "Date": "2024-06-02", "Team": "Sound Team", "Position": "FOH"},
        {"Full Name": "Nobody Here", "Date": "2024-06-02", "Team": "Sound Team"},
        {"Full Name": "John Doe", "Date": "2099-01-01", "Team": "Sound Team"},
        {"Full Name": "John Doe", "Date": "2024-06-02", "Team": "No Such Team"},
    ]
    resolved, problems = match_rows(rows, PEOPLE, PLANS, TEAMS)
    assert len(resolved) == 1
    assert resolved[0]["person_id"] == "5678"
    assert resolved[0]["team_id"] == "t1"
    assert resolved[0]["position"] == "FOH"
    assert len(problems) == 3


# ── roster sync ──────────────────────────────────────────────────────────────


def _ptpa(assignment_id: str, person_id: str, position_id: str = "tp1") -> dict:
    return {
        "id": assignment_id,
        "type": "PersonTeamPositionAssignment",
        "attributes": {},
        "relationships": {
            "person": {"data": {"id": person_id, "type": "Person"}},
            "team_position": {"data": {"id": position_id, "type": "TeamPosition"}},
        },
    }


def test_diff_roster_adds_and_removes():
    csv_ids = {"5678": "John Doe", "999": "New Person"}
    current = [_ptpa("a1", "5678"), _ptpa("a2", "42")]
    to_add, to_remove = diff_roster(csv_ids, current)
    assert to_add == [("999", "New Person")]
    assert [(aid, pid) for aid, pid, _ in to_remove] == [("a2", "42")]


def test_diff_roster_no_changes():
    csv_ids = {"5678": "John Doe"}
    current = [_ptpa("a1", "5678")]
    assert diff_roster(csv_ids, current) == ([], [])


# ── template copy ────────────────────────────────────────────────────────────


def test_build_import_payload():
    payload = build_import_payload("77", ["88", "99"])
    attrs = payload["data"]["attributes"]
    assert attrs["source_id"] == 77
    assert attrs["copy_people"] is True
    assert attrs["additional_target_ids"] == [88, 99]


# ── auto blockout ────────────────────────────────────────────────────────────


def _pp(person_id: str, status: str) -> PlanPerson:
    return PlanPerson(
        id="x",
        person_id=person_id,
        person_name=f"Person {person_id}",
        status=status,
        team_id="t1",
        team_name="Sound",
        position="Tech",
    )


def test_find_repeated_decliners_threshold():
    members = [_pp("p1", "D"), _pp("p1", "D"), _pp("p1", "D"), _pp("p2", "D"), _pp("p3", "C")]
    result = find_repeated_decliners(members, min_declines=3)
    assert len(result) == 1
    assert result[0]["person_id"] == "p1"
    assert result[0]["declines"] == 3


def test_find_repeated_decliners_ignores_confirmed():
    members = [_pp("p1", "C")] * 5
    assert find_repeated_decliners(members, min_declines=1) == []
