"""Tests for People-product features (duplicates, compliance, bulk fields)."""
from people.background_checks import build_compliance_records
from people.bulk_fields import plan_updates
from people.duplicates import detect_duplicates


def _person_rec(pid, first, last, birthdate="", emails=(), status="active"):
    return {
        "data": {
            "id": pid,
            "type": "Person",
            "attributes": {
                "first_name": first,
                "last_name": last,
                "name": f"{first} {last}",
                "birthdate": birthdate,
                "status": status,
            },
        },
        "included": [
            {"id": f"e{i}", "type": "Email", "attributes": {"address": addr}}
            for i, addr in enumerate(emails)
        ],
    }


# ── duplicate detection ──────────────────────────────────────────────────────


def test_detects_same_email():
    records = [
        _person_rec("1", "John", "Doe", emails=["jd@example.com"]),
        _person_rec("2", "Johnny", "Doe", emails=["jd@example.com"]),
    ]
    [dup] = detect_duplicates(records)
    assert "same email" in dup["reason"]


def test_detects_identical_name():
    records = [
        _person_rec("1", "John", "Doe"),
        _person_rec("2", "John", "Doe"),
    ]
    [dup] = detect_duplicates(records)
    assert "identical name" in dup["reason"]


def test_detects_last_name_plus_birthdate():
    records = [
        _person_rec("1", "Jonathan", "Doe", birthdate="1990-01-01"),
        _person_rec("2", "Jon", "Doe", birthdate="1990-01-01"),
    ]
    dups = detect_duplicates(records)
    assert any("birthdate" in d["reason"] for d in dups)


def test_detects_similar_names():
    records = [
        _person_rec("1", "Katherine", "Johnson"),
        _person_rec("2", "Katherin", "Johnson"),
    ]
    dups = detect_duplicates(records)
    assert any("similar names" in d["reason"] for d in dups)


def test_no_false_positive_on_distinct_people():
    records = [
        _person_rec("1", "John", "Doe", birthdate="1990-01-01", emails=["a@x.com"]),
        _person_rec("2", "Mary", "Smith", birthdate="1985-05-05", emails=["b@x.com"]),
    ]
    assert detect_duplicates(records) == []


def test_pair_flagged_once():
    records = [
        _person_rec("1", "John", "Doe", birthdate="1990-01-01", emails=["jd@x.com"]),
        _person_rec("2", "John", "Doe", birthdate="1990-01-01", emails=["jd@x.com"]),
    ]
    assert len(detect_duplicates(records)) == 1


# ── background checks ────────────────────────────────────────────────────────


def _people_profile(name, passed):
    first, last = name.split(" ", 1)
    return {
        "id": "x",
        "attributes": {
            "name": name,
            "first_name": first,
            "last_name": last,
            "passed_background_check": passed,
            "status": "active",
        },
    }


def test_compliance_flags_unpassed_and_unmatched():
    services_people = [
        {"id": "s1", "attributes": {"full_name": "John Doe"}},
        {"id": "s2", "attributes": {"full_name": "Mary Smith"}},
        {"id": "s3", "attributes": {"full_name": "Ghost Person"}},
    ]
    people = [_people_profile("John Doe", True), _people_profile("Mary Smith", False)]
    records = build_compliance_records(services_people, people)
    issues = {r["person_name"]: r["issue"] for r in records}
    assert "John Doe" not in issues
    assert issues["Mary Smith"] == "no passed background check on file"
    assert issues["Ghost Person"] == "no matching People profile found"


# ── bulk field updates ───────────────────────────────────────────────────────

FIELD_DEFS = [
    {"id": "fd1", "attributes": {"name": "Volunteer Status"}},
    {"id": "fd2", "attributes": {"name": "T-Shirt Size"}},
]

PEOPLE = [
    {
        "id": "1",
        "attributes": {"first_name": "John", "last_name": "Doe", "full_name": "John Doe", "name": "John Doe"},
    }
]


def test_plan_updates_resolves_fields():
    rows = [{"Full Name": "John Doe", "Volunteer Status": "Active", "T-Shirt Size": "L"}]
    updates, problems = plan_updates(rows, PEOPLE, FIELD_DEFS)
    assert problems == []
    assert {(u["field_definition_id"], u["value"]) for u in updates} == {
        ("fd1", "Active"),
        ("fd2", "L"),
    }


def test_plan_updates_reports_unknown_person_and_field():
    rows = [
        {"Full Name": "Nobody Here", "Volunteer Status": "Active"},
        {"Full Name": "John Doe", "Shoe Size": "12"},
    ]
    updates, problems = plan_updates(rows, PEOPLE, FIELD_DEFS)
    assert updates == []
    assert len(problems) == 2


def test_plan_updates_skips_empty_values():
    rows = [{"Full Name": "John Doe", "Volunteer Status": "", "T-Shirt Size": "  "}]
    updates, problems = plan_updates(rows, PEOPLE, FIELD_DEFS)
    assert updates == [] and problems == []
