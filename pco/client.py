"""Thin wrapper around pypco for creating and working with the PCO API client."""

import json
import pypco


def create_client(context: dict) -> pypco.PCO:
    """Create an authenticated pypco client from a context dict.

    Args:
        context: Dict with 'application_id' and 'secret' keys from a .cxt file.

    Returns:
        An authenticated pypco.PCO instance.

    Raises:
        SystemExit: If the context is missing required credentials.
    """
    app_id = context.get("application_id")
    secret = context.get("secret")

    if not app_id or not secret:
        print("Invalid context — missing application_id or secret.")
        raise SystemExit(1)

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


def get_all_services_people(pco: pypco.PCO) -> list[dict]:
    """Retrieve every person from Planning Center Services.

    Returns:
        A flat list of person resource dicts.
    """
    return _iterate_to_list(pco, "/services/v2/people")
