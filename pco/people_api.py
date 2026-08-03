"""Helpers for the Planning Center People API (/people/v2).

Docs: https://api.planningcenteronline.com/docs/apps/people/versions/2024-09-12
"""
from __future__ import annotations

import pypco

from pco.client import _iterate_to_list


def get_people_with_emails(pco: pypco.PCO) -> list[dict]:
    """Retrieve every person with their Email resources attached.

    pypco injects each record's included resources, so every returned dict is
    ``{"data": person, "included": [Email, ...]}``.
    """
    return list(pco.iterate("/people/v2/people", per_page=100, include="emails"))


def get_all_people(pco: pypco.PCO) -> list[dict]:
    """GET /people/v2/people (all pages)."""
    return _iterate_to_list(pco, "/people/v2/people")


def get_field_definitions(pco: pypco.PCO) -> list[dict]:
    """GET /people/v2/field_definitions"""
    return _iterate_to_list(pco, "/people/v2/field_definitions")


def get_person_field_data(pco: pypco.PCO, person_id: str) -> list[dict]:
    """GET /people/v2/people/{id}/field_data"""
    return _iterate_to_list(pco, f"/people/v2/people/{person_id}/field_data")


def set_field_datum(
    pco: pypco.PCO, person_id: str, field_definition_id: str, value: str, existing_id: str | None
) -> None:
    """Create or update a custom-field value for a person.

    POST  /people/v2/people/{id}/field_data          (assignable: value, field_definition_id)
    PATCH /people/v2/people/{id}/field_data/{fd_id}  (assignable: value)
    Docs: https://api.planningcenteronline.com/docs/apps/people/versions/2024-09-12/vertices/field_datum
    """
    if existing_id:
        payload = {"data": {"type": "FieldDatum", "id": existing_id, "attributes": {"value": value}}}
        pco.patch(f"/people/v2/people/{person_id}/field_data/{existing_id}", payload=payload)
    else:
        payload = {
            "data": {
                "type": "FieldDatum",
                "attributes": {"value": value, "field_definition_id": field_definition_id},
            }
        }
        pco.post(f"/people/v2/people/{person_id}/field_data", payload=payload)


def get_workflows(pco: pypco.PCO) -> list[dict]:
    """GET /people/v2/workflows"""
    return _iterate_to_list(pco, "/people/v2/workflows")


def get_overdue_cards(pco: pypco.PCO, workflow_id: str) -> list[dict]:
    """GET /people/v2/workflows/{id}/cards?where[overdue]=true with person included."""
    return list(
        pco.iterate(
            f"/people/v2/workflows/{workflow_id}/cards",
            per_page=100,
            include="person",
            **{"where[overdue]": "true"},
        )
    )


def create_workflow_card(pco: pypco.PCO, workflow_id: str, person_id: str) -> dict:
    """POST /people/v2/workflows/{id}/cards (assignable: person_id, assignee_id, sticky_assignment).

    Docs: https://api.planningcenteronline.com/docs/apps/people/versions/2024-09-12/vertices/workflow_card
    """
    payload = {"data": {"type": "WorkflowCard", "attributes": {"person_id": person_id}}}
    return pco.post(f"/people/v2/workflows/{workflow_id}/cards", payload=payload)


def get_forms(pco: pypco.PCO) -> list[dict]:
    """GET /people/v2/forms"""
    return _iterate_to_list(pco, "/people/v2/forms")


def get_form_submissions(pco: pypco.PCO, form_id: str) -> list[dict]:
    """GET /people/v2/forms/{id}/form_submissions with person included."""
    return list(
        pco.iterate(f"/people/v2/forms/{form_id}/form_submissions", per_page=100, include="person")
    )
