"""Domain dataclasses for Planning Center API resources.

Shapes mirror the documented API exactly:
https://api.planningcenteronline.com/docs/apps/services/versions/2018-11-01
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from pco.client import rel_id

# PlanPerson.status values (docs accept both short and long forms).
STATUS_CONFIRMED = "C"
STATUS_UNCONFIRMED = "U"
STATUS_DECLINED = "D"

_STATUS_NORMALIZE = {
    "confirmed": STATUS_CONFIRMED,
    "unconfirmed": STATUS_UNCONFIRMED,
    "declined": STATUS_DECLINED,
}


def _parse_dt(value: str | None) -> datetime | None:
    """Parse an ISO 8601 string to a UTC-aware datetime, or return None."""
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def normalize_status(value: str) -> str:
    """Normalize a PlanPerson status to its single-letter form (C/U/D)."""
    return _STATUS_NORMALIZE.get(value.strip().lower(), value.strip())


@dataclass
class Plan:
    id: str
    name: str
    sort_date: datetime
    dates: str
    service_type_id: str
    service_type_name: str = ""

    @classmethod
    def from_api(
        cls,
        data: dict,
        service_type_id: str = "",
        service_type_name: str = "",
    ) -> Plan:
        attrs = data["attributes"]
        sort_date = _parse_dt(attrs.get("sort_date")) or datetime.now(UTC)
        return cls(
            id=data["id"],
            name=attrs.get("title") or attrs.get("series_title") or "",
            sort_date=sort_date,
            dates=attrs.get("dates", ""),
            service_type_id=service_type_id,
            service_type_name=service_type_name,
        )


@dataclass
class Person:
    id: str
    first_name: str
    last_name: str
    full_name: str

    @property
    def sort_key(self) -> str:
        return self.full_name.casefold()

    @classmethod
    def from_api(cls, data: dict) -> Person:
        attrs = data["attributes"]
        first_name = attrs.get("first_name", "")
        last_name = attrs.get("last_name", "")
        full_name = attrs.get("full_name") or f"{first_name} {last_name}".strip()
        return cls(id=data["id"], first_name=first_name, last_name=last_name, full_name=full_name)


@dataclass
class PlanPerson:
    """A person scheduled onto a plan (URL path segment: team_members).

    ``status`` is C (confirmed), U (unconfirmed) or D (declined); when
    declined, ``status_updated_at`` is the decline time and ``decline_reason``
    may carry text. There is no separate declined_at field in the API.
    """

    id: str
    person_id: str
    person_name: str
    status: str
    team_id: str
    team_name: str
    position: str
    decline_reason: str = ""
    status_updated_at: datetime | None = None
    notification_sent_at: datetime | None = None
    notification_read_at: datetime | None = None
    plan_id: str = ""
    plan_date: datetime | None = None
    service_type_id: str = ""
    service_type_name: str = ""

    @property
    def is_confirmed(self) -> bool:
        return normalize_status(self.status) == STATUS_CONFIRMED

    @property
    def is_declined(self) -> bool:
        return normalize_status(self.status) == STATUS_DECLINED

    @property
    def is_unconfirmed(self) -> bool:
        return normalize_status(self.status) == STATUS_UNCONFIRMED

    @classmethod
    def from_api(
        cls,
        data: dict,
        team_map: dict[str, str] | None = None,
        plan_id: str = "",
        plan_date: datetime | None = None,
        service_type_id: str = "",
        service_type_name: str = "",
    ) -> PlanPerson:
        attrs = data["attributes"]
        team_id = rel_id(data, "team")
        team_name = (team_map or {}).get(team_id, attrs.get("team_name", ""))

        return cls(
            id=data["id"],
            person_id=rel_id(data, "person"),
            person_name=attrs.get("name", ""),
            status=attrs.get("status", ""),
            team_id=team_id,
            team_name=team_name,
            position=attrs.get("team_position_name", ""),
            decline_reason=attrs.get("decline_reason") or "",
            status_updated_at=_parse_dt(attrs.get("status_updated_at")),
            notification_sent_at=_parse_dt(attrs.get("notification_sent_at")),
            notification_read_at=_parse_dt(attrs.get("notification_read_at")),
            plan_id=plan_id,
            plan_date=plan_date,
            service_type_id=service_type_id,
            service_type_name=service_type_name,
        )


@dataclass
class Blockout:
    id: str
    person_id: str
    starts_at: datetime
    ends_at: datetime
    reason: str

    def contains(self, dt: datetime) -> bool:
        """Return True if dt falls within this blockout window (inclusive)."""
        d = dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt
        return self.starts_at <= d <= self.ends_at

    @classmethod
    def from_api(cls, data: dict, person_id: str = "") -> Blockout:
        attrs = data["attributes"]
        starts_at = _parse_dt(attrs["starts_at"]) or datetime.now(UTC)
        ends_at = _parse_dt(attrs["ends_at"]) or datetime.now(UTC)
        return cls(
            id=data["id"],
            person_id=person_id,
            starts_at=starts_at,
            ends_at=ends_at,
            reason=attrs.get("reason") or "",
        )


@dataclass
class NeededPosition:
    """An amount of *unfilled* positions on a plan.

    Documented attributes are only quantity, scheduled_to and
    team_position_name — quantity is already the open-slot count.
    """

    id: str
    plan_id: str
    team_id: str
    team_name: str
    position_name: str
    quantity: int

    @classmethod
    def from_api(
        cls,
        data: dict,
        plan_id: str = "",
        team_name: str = "",
    ) -> NeededPosition:
        attrs = data["attributes"]
        return cls(
            id=data["id"],
            plan_id=plan_id,
            team_id=rel_id(data, "team"),
            team_name=team_name,
            position_name=attrs.get("team_position_name", ""),
            quantity=int(attrs.get("quantity") or 0),
        )


@dataclass
class TeamPositionAssignment:
    """PersonTeamPositionAssignment — links a person to a team position."""

    id: str
    person_id: str
    team_position_id: str
    schedule_preference: str = ""
    preferred_weeks: list[str] = field(default_factory=list)

    @classmethod
    def from_api(cls, data: dict) -> TeamPositionAssignment:
        attrs = data.get("attributes", {})
        return cls(
            id=data["id"],
            person_id=rel_id(data, "person"),
            team_position_id=rel_id(data, "team_position"),
            schedule_preference=attrs.get("schedule_preference") or "",
            preferred_weeks=list(attrs.get("preferred_weeks") or []),
        )
