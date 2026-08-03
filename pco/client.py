"""Thin wrapper around pypco for creating and working with the PCO API client.

Every endpoint helper cites its documentation page. All list helpers paginate
with per_page=100 (the API maximum). pypco transparently retries rate-limited
requests (HTTP 429 honoring Retry-After); the PCO limit is 100 requests / 20 s.
"""

import os

import keyring
import pypco

_KEYRING_SERVICE = "planning-center-tools"


# ── Credentials ──────────────────────────────────────────────────────────────


def setup_credentials() -> None:
    """Prompt the user for PCO API credentials and store them in the system keyring."""
    print(
        "PCO API credentials not found. Enter them now"
        " (from https://api.planningcenteronline.com/personal_access_tokens)."
    )
    app_id = input("  Application ID: ").strip()
    secret = input("  Secret: ").strip()

    if not app_id or not secret:
        print("Both fields are required.")
        return setup_credentials()

    keyring.set_password(_KEYRING_SERVICE, "application_id", app_id)
    keyring.set_password(_KEYRING_SERVICE, "secret", secret)
    print("Credentials saved to keyring.")


def create_client() -> pypco.PCO:
    """Create an authenticated pypco client.

    Credential resolution order:
      1. PCO_APP_ID / PCO_SECRET environment variables (for CI / scripting)
      2. System keyring (interactive use; prompts and stores on first run)

    Returns:
        An authenticated pypco.PCO instance.
    """
    app_id = os.environ.get("PCO_APP_ID") or keyring.get_password(_KEYRING_SERVICE, "application_id")
    secret = os.environ.get("PCO_SECRET") or keyring.get_password(_KEYRING_SERVICE, "secret")

    if not app_id or not secret:
        setup_credentials()
        app_id = keyring.get_password(_KEYRING_SERVICE, "application_id")
        secret = keyring.get_password(_KEYRING_SERVICE, "secret")

    return pypco.PCO(app_id, secret)


# ── Cache ────────────────────────────────────────────────────────────────────

_cache: dict[str, list[dict]] = {}


def clear_cache() -> None:
    """Clear the whole module-level response cache."""
    _cache.clear()


def invalidate_cache(prefix: str) -> None:
    """Drop every cached entry whose key starts with *prefix*.

    Call after a write so subsequent reads see fresh data (e.g. after POSTing
    a blockout, invalidate that person's blockout listing).
    """
    for key in [k for k in _cache if k.startswith(prefix)]:
        del _cache[key]


# ── Generic helpers ──────────────────────────────────────────────────────────


def _iterate_to_list(pco: pypco.PCO, endpoint: str, **params: str) -> list[dict]:
    """Paginate through an API endpoint and return all resource dicts."""
    return [item["data"] for item in pco.iterate(endpoint, per_page=100, **params)]


def _cached(pco: pypco.PCO, endpoint: str, **params: str) -> list[dict]:
    """Return the cached list for endpoint+params, fetching on first call."""
    key = endpoint + ("?" + "&".join(f"{k}={v}" for k, v in sorted(params.items())) if params else "")
    if key in _cache:
        return _cache[key]
    result = _iterate_to_list(pco, endpoint, **params)
    _cache[key] = result
    return result


def rel_id(resource: dict, name: str) -> str:
    """Null-safe extraction of a to-one relationship ID from a JSON:API resource.

    Empty relationships come back as ``"data": null``, so a plain
    ``.get("data", {})`` chain would crash on None.
    """
    rel = (resource.get("relationships", {}).get(name, {}) or {}).get("data") or {}
    return rel.get("id", "")


# ── Services API: service types & plans ──────────────────────────────────────
# Docs: https://api.planningcenteronline.com/docs/apps/services/versions/2018-11-01/vertices/service_type


def get_all_service_types(pco: pypco.PCO) -> list[dict]:
    """Retrieve every service type from Planning Center Services."""
    return _cached(pco, "/services/v2/service_types")


def pick_service_type(pco: pypco.PCO, choice: int | None = None) -> dict:
    """Interactively prompt the user to select a service type.

    Args:
        pco: An authenticated pypco.PCO instance.
        choice: Optional pre-selected 1-based index.

    Returns:
        The selected service-type resource dict.
    """
    service_types = get_all_service_types(pco)
    print("Choose a service type:")
    for i, st in enumerate(service_types, 1):
        print(f"  {i}. {st['attributes']['name']}")

    if choice is None:
        choice = int(input("Enter the number of your choice: "))

    try:
        return service_types[choice - 1]
    except (IndexError, ValueError):
        print("Invalid choice. Please enter a number from the list.")
        return pick_service_type(pco)


def pick_service_types(pco: pypco.PCO) -> list[dict]:
    """Prompt for one service type, all of them, or those set in config.toml.

    Returns:
        A list of service-type resource dicts.
    """
    from pco.config import get_config

    configured = get_config().org.service_type_ids
    print("Scope:")
    print("  1. One service type (pick from list)")
    print("  2. All service types")
    if configured:
        print("  3. Service types from config.toml")
    choice = input("Enter your choice: ").strip()

    if choice == "1":
        return [pick_service_type(pco)]
    if choice == "2":
        return get_all_service_types(pco)
    if choice == "3" and configured:
        return [st for st in get_all_service_types(pco) if st["id"] in configured]
    print("Invalid choice.")
    return pick_service_types(pco)


def get_plans(pco: pypco.PCO, service_type_id: str, order: str = "-sort_date") -> list[dict]:
    """Retrieve all plans for a service type, paginated.

    Docs: https://api.planningcenteronline.com/docs/apps/services/versions/2018-11-01/vertices/plan
    """
    return _iterate_to_list(
        pco, f"/services/v2/service_types/{service_type_id}/plans", order=order
    )


def get_future_plans(pco: pypco.PCO, service_type_id: str) -> list[dict]:
    """Retrieve upcoming plans (soonest first) for a service type.

    Uses the documented named filter: ``?filter=future&order=sort_date``.
    """
    return _iterate_to_list(
        pco,
        f"/services/v2/service_types/{service_type_id}/plans",
        **{"filter": "future", "order": "sort_date"},
    )


def get_plans_between(pco: pypco.PCO, service_type_id: str, after: str, before: str) -> list[dict]:
    """Retrieve plans within a date range (inclusive named filters).

    Correct filter form per docs: ``?filter=after,before&after=DATE&before=DATE``.
    """
    return _iterate_to_list(
        pco,
        f"/services/v2/service_types/{service_type_id}/plans",
        **{"filter": "after,before", "after": after, "before": before, "order": "sort_date"},
    )


# ── Services API: plan people (a.k.a. team members) ──────────────────────────
# Resource type is PlanPerson; the URL path segment is "team_members".
# Docs: https://api.planningcenteronline.com/docs/apps/services/versions/2018-11-01/vertices/plan_person


def get_team_members(
    pco: pypco.PCO, service_type_id: str, plan_id: str, filter: str | None = None
) -> list[dict]:
    """Retrieve all PlanPerson records for a plan.

    Args:
        filter: Optional named filter — one of ``confirmed``, ``not_archived``,
            ``not_declined``, ``not_deleted`` (comma-separable).
    """
    endpoint = f"/services/v2/service_types/{service_type_id}/plans/{plan_id}/team_members"
    params = {"filter": filter} if filter else {}
    return _iterate_to_list(pco, endpoint, **params)


def get_template_members(
    pco: pypco.PCO, service_type_id: str, template_id: str
) -> tuple[list[dict], dict[str, str]]:
    """Retrieve all team members for a plan template (paginated).

    Uses ``?include=team`` so that the response includes team resources,
    allowing us to build a team-ID → team-name lookup (which also covers
    archived teams that wouldn't appear in the normal teams listing).

    Returns:
        A tuple of (members, team_map) where *members* is a flat list of
        PlanPerson resource dicts and *team_map* maps team IDs to names.
    """
    endpoint = (
        f"/services/v2/service_types/{service_type_id}"
        f"/plan_templates/{template_id}/team_members"
    )
    members: list[dict] = []
    team_map: dict[str, str] = {}
    for page in pco.iterate(endpoint, per_page=100, include="team"):
        members.append(page["data"])
        for inc in page.get("included", []):
            if inc["type"] == "Team":
                team_map[inc["id"]] = inc["attributes"]["name"]
    return members, team_map


# ── Services API: people, blockouts & schedules ──────────────────────────────


def get_all_services_people(pco: pypco.PCO) -> list[dict]:
    """Retrieve every person from Planning Center Services.

    Docs: https://api.planningcenteronline.com/docs/apps/services/versions/2018-11-01/vertices/person
    """
    return _cached(pco, "/services/v2/people")


def get_person_blockouts(pco: pypco.PCO, person_id: str) -> list[dict]:
    """Retrieve all existing blockout dates for a person (cached).

    Docs: https://api.planningcenteronline.com/docs/apps/services/versions/2018-11-01/vertices/blockout
    """
    return _cached(pco, f"/services/v2/people/{person_id}/blockouts")


def post_blockout(pco: pypco.PCO, person_id: str, payload: dict) -> dict:
    """POST a blockout for a person and invalidate their cached blockout list."""
    result = pco.post(f"/services/v2/people/{person_id}/blockouts", payload=payload)
    invalidate_cache(f"/services/v2/people/{person_id}/blockouts")
    return result


# ── Services API: teams & rosters ────────────────────────────────────────────
# Docs: https://api.planningcenteronline.com/docs/apps/services/versions/2018-11-01/vertices/team
# Docs: https://api.planningcenteronline.com/docs/apps/services/versions/2018-11-01/vertices/person_team_position_assignment


def get_teams(pco: pypco.PCO, service_type_id: str) -> list[dict]:
    """GET /services/v2/service_types/{id}/teams"""
    return _iterate_to_list(pco, f"/services/v2/service_types/{service_type_id}/teams")


def get_team_people(pco: pypco.PCO, team_id: str) -> list[dict]:
    """GET /services/v2/teams/{id}/people — the team roster (Person resources)."""
    return _iterate_to_list(pco, f"/services/v2/teams/{team_id}/people")


def get_team_positions(pco: pypco.PCO, team_id: str) -> list[dict]:
    """GET /services/v2/teams/{id}/team_positions"""
    return _iterate_to_list(pco, f"/services/v2/teams/{team_id}/team_positions")


def get_team_position_assignments(pco: pypco.PCO, team_id: str) -> list[dict]:
    """GET /services/v2/teams/{id}/person_team_position_assignments"""
    return _iterate_to_list(
        pco, f"/services/v2/teams/{team_id}/person_team_position_assignments"
    )


# ── Services API: needed positions ───────────────────────────────────────────


def get_needed_positions(pco: pypco.PCO, service_type_id: str, plan_id: str) -> list[dict]:
    """GET /services/v2/service_types/{st}/plans/{plan}/needed_positions

    Each NeededPosition *is* an amount of unfilled positions (attributes:
    quantity, scheduled_to, team_position_name — there is no accepted_count).
    Docs: https://api.planningcenteronline.com/docs/apps/services/versions/2018-11-01/vertices/needed_position
    """
    return _iterate_to_list(
        pco,
        f"/services/v2/service_types/{service_type_id}/plans/{plan_id}/needed_positions",
        include="team",
    )
