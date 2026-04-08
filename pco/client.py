"""Thin wrapper around pypco for creating and working with the PCO API client."""

import keyring
import pypco

_KEYRING_SERVICE = "planning-center-tools"


def setup_credentials() -> None:
    """Prompt the user for PCO API credentials and store them in the system keyring."""
    print("PCO API credentials not found. Enter them now (from https://api.planningcenteronline.com/personal_access_tokens).")
    app_id = input("  Application ID: ").strip()
    secret = input("  Secret: ").strip()

    if not app_id or not secret:
        print("Both fields are required.")
        return setup_credentials()

    keyring.set_password(_KEYRING_SERVICE, "application_id", app_id)
    keyring.set_password(_KEYRING_SERVICE, "secret", secret)
    print("Credentials saved to keyring.")


def create_client() -> pypco.PCO:
    """Create an authenticated pypco client using credentials from the system keyring.

    If credentials are not found, the user is prompted to enter and store them.

    Returns:
        An authenticated pypco.PCO instance.
    """
    app_id = keyring.get_password(_KEYRING_SERVICE, "application_id")
    secret = keyring.get_password(_KEYRING_SERVICE, "secret")

    if not app_id or not secret:
        setup_credentials()
        app_id = keyring.get_password(_KEYRING_SERVICE, "application_id")
        secret = keyring.get_password(_KEYRING_SERVICE, "secret")

    return pypco.PCO(app_id, secret)


def _iterate_to_list(pco: pypco.PCO, endpoint: str) -> list[dict]:
    """Paginate through an API endpoint and return all resource dicts."""
    return [item["data"] for item in pco.iterate(endpoint)]


def get_all_service_types(pco: pypco.PCO) -> list[dict]:
    """Retrieve every service type from Planning Center Services.

    Args:
        pco: An authenticated pypco.PCO instance.

    Returns:
        A list of service-type resource dicts.
    """
    return _iterate_to_list(pco, "/services/v2/service_types")


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


def get_plans(pco: pypco.PCO, service_type_id: str, order: str = "-sort_date") -> list[dict]:
    """Retrieve plans for a service type.

    Args:
        pco: An authenticated pypco.PCO instance.
        service_type_id: The service type ID.
        order: Sort order string (default: newest first).

    Returns:
        A list of plan resource dicts.
    """
    response = pco.get(f"/services/v2/service_types/{service_type_id}/plans?order={order}")
    return response.get("data", [])


def get_team_members(pco: pypco.PCO, service_type_id: str, plan_id: str) -> list[dict]:
    """Retrieve all team members for a given plan.

    Args:
        pco: An authenticated pypco.PCO instance.
        service_type_id: The service type ID.
        plan_id: The plan ID.

    Returns:
        A flat list of team-member resource dicts.
    """
    endpoint = f"/services/v2/service_types/{service_type_id}/plans/{plan_id}/team_members"
    return _iterate_to_list(pco, endpoint)


def get_template_members(
    pco: pypco.PCO, service_type_id: str, template_id: str
) -> tuple[list[dict], dict[str, str]]:
    """Retrieve all team members for a plan template (paginated).

    Uses ``?include=team`` so that the response includes team resources,
    allowing us to build a team-ID → team-name lookup (which also covers
    archived teams that wouldn't appear in the normal teams listing).

    Args:
        pco: An authenticated pypco.PCO instance.
        service_type_id: The service type ID.
        template_id: The plan template ID.

    Returns:
        A tuple of (members, team_map) where *members* is a flat list of
        team-member resource dicts and *team_map* maps team IDs to names.
    """
    endpoint = (
        f"/services/v2/service_types/{service_type_id}"
        f"/plan_templates/{template_id}/team_members?include=team"
    )
    members: list[dict] = []
    team_map: dict[str, str] = {}
    for page in pco.iterate(endpoint):
        members.append(page["data"])
        for inc in page.get("included", []):
            if inc["type"] == "Team":
                team_map[inc["id"]] = inc["attributes"]["name"]
    return members, team_map


def get_all_services_people(pco: pypco.PCO) -> list[dict]:
    """Retrieve every person from Planning Center Services.

    Returns:
        A flat list of person resource dicts.
    """
    return _iterate_to_list(pco, "/services/v2/people")


def get_person_blockouts(pco: pypco.PCO, person_id: str) -> list[dict]:
    """Retrieve all existing blockout dates for a person.

    Args:
        pco: An authenticated pypco.PCO instance.
        person_id: The Services person ID.

    Returns:
        A flat list of blockout resource dicts.
    """
    return _iterate_to_list(pco, f"/services/v2/people/{person_id}/blockouts")
