"""Canned PCO API response dicts for tests.

Shapes copy the documented examples at
https://api.planningcenteronline.com/docs/apps/services/versions/2018-11-01
— keep them faithful to the real API. Do not invent attributes.
"""

# Plan — real attribute is "title" (there is no "name" on Plan).
PLAN_DATA: dict = {
    "id": "1234",
    "type": "Plan",
    "attributes": {
        "title": "Weekend Service",
        "series_title": "",
        "sort_date": "2024-06-01T17:00:00Z",
        "dates": "June 1, 2024",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-05-01T00:00:00Z",
    },
    "relationships": {},
}

PERSON_DATA: dict = {
    "id": "5678",
    "type": "Person",
    "attributes": {
        "first_name": "John",
        "last_name": "Doe",
        "full_name": "John Doe",
        "created_at": "2023-01-01T00:00:00Z",
    },
    "relationships": {},
}

# PlanPerson — resource type for the plans/{id}/team_members path.
# status: 'C' | 'U' | 'D'; decline info lives in decline_reason + status_updated_at.
PLAN_PERSON_DATA: dict = {
    "id": "9012",
    "type": "PlanPerson",
    "attributes": {
        "name": "John Doe",
        "status": "C",
        "team_position_name": "Sound",
        "decline_reason": None,
        "status_updated_at": "2024-05-20T12:00:00Z",
        "notification_sent_at": "2024-05-18T12:00:00Z",
        "notification_read_at": "2024-05-19T08:00:00Z",
    },
    "relationships": {
        "person": {"data": {"id": "5678", "type": "Person"}},
        "team": {"data": {"id": "3456", "type": "Team"}},
        "plan": {"data": {"id": "1234", "type": "Plan"}},
    },
}

PLAN_PERSON_DECLINED: dict = {
    "id": "9013",
    "type": "PlanPerson",
    "attributes": {
        "name": "Jane Roe",
        "status": "D",
        "team_position_name": "Vocals",
        "decline_reason": "Out of town",
        "status_updated_at": "2024-05-21T09:00:00Z",
        "notification_sent_at": "2024-05-18T12:00:00Z",
        "notification_read_at": None,
    },
    "relationships": {
        "person": {"data": {"id": "5679", "type": "Person"}},
        "team": {"data": {"id": "3456", "type": "Team"}},
        "plan": {"data": {"id": "1234", "type": "Plan"}},
    },
}

# Unassigned placeholder slot — person relationship is null (real API behavior).
PLAN_PERSON_NULL_PERSON: dict = {
    "id": "9014",
    "type": "PlanPerson",
    "attributes": {
        "name": "",
        "status": "U",
        "team_position_name": "Drums",
        "decline_reason": None,
        "status_updated_at": None,
        "notification_sent_at": None,
        "notification_read_at": None,
    },
    "relationships": {
        "person": {"data": None},
        "team": {"data": {"id": "3456", "type": "Team"}},
        "plan": {"data": {"id": "1234", "type": "Plan"}},
    },
}

BLOCKOUT_DATA: dict = {
    "id": "7890",
    "type": "Blockout",
    "attributes": {
        "starts_at": "2024-07-01T00:00:00Z",
        "ends_at": "2024-07-14T00:00:00Z",
        "reason": "Vacation",
        "repeat_frequency": "no_repeat",
        "share": True,
    },
    "relationships": {},
}

# NeededPosition — attributes are ONLY quantity, scheduled_to, team_position_name.
NEEDED_POSITION_DATA: dict = {
    "id": "1122",
    "type": "NeededPosition",
    "attributes": {
        "team_position_name": "Worship Leader",
        "quantity": 2,
        "scheduled_to": "plan",
    },
    "relationships": {
        "team": {"data": {"id": "3456", "type": "Team"}},
        "plan": {"data": {"id": "1234", "type": "Plan"}},
    },
}

TEAM_DATA: dict = {
    "id": "3456",
    "type": "Team",
    "attributes": {
        "name": "Sound Team",
        "schedule_to": "plan",
    },
    "relationships": {},
}

# PersonTeamPositionAssignment — how team rosters are managed via API.
PTPA_DATA: dict = {
    "id": "4455",
    "type": "PersonTeamPositionAssignment",
    "attributes": {
        "schedule_preference": "Every other week",
        "preferred_weeks": [],
    },
    "relationships": {
        "person": {"data": {"id": "5678", "type": "Person"}},
        "team_position": {"data": {"id": "6677", "type": "TeamPosition"}},
    },
}


class FakePCO:
    """Minimal pypco.PCO stand-in: maps endpoint → list of resource dicts.

    ``iterate`` yields ``{"data": resource}`` records like the real client.
    Registered endpoints match on path only (query params from kwargs are
    recorded on ``.calls`` for assertion).
    """

    def __init__(self, responses: dict[str, list[dict]] | None = None):
        self.responses = responses or {}
        self.calls: list[tuple[str, str, dict]] = []
        self.posted: list[tuple[str, dict]] = []
        self.deleted: list[str] = []

    def iterate(self, url: str, offset: int = 0, per_page: int = 25, **params):
        self.calls.append(("GET", url, params))
        for item in self.responses.get(url, []):
            yield {"data": item, "included": [], "meta": {}}

    def get(self, url: str, **params):
        self.calls.append(("GET", url, params))
        return {"data": self.responses.get(url, [])}

    def post(self, url: str, payload: dict | None = None, **params):
        self.calls.append(("POST", url, params))
        self.posted.append((url, payload or {}))
        return {"data": {"id": "new", "type": "Unknown", "attributes": {}}}

    def delete(self, url: str, **params):
        self.calls.append(("DELETE", url, params))
        self.deleted.append(url)

    @staticmethod
    def template(object_type: str, attributes: dict | None = None) -> dict:
        return {"data": {"type": object_type, "attributes": attributes or {}}}
