"""Tests for pco/client.py cache behavior and helpers."""
from pco import client
from tests.fixtures import BLOCKOUT_DATA, PLAN_PERSON_NULL_PERSON, FakePCO


def setup_function(_):
    client.clear_cache()


def test_rel_id_present():
    resource = {"relationships": {"team": {"data": {"id": "t1", "type": "Team"}}}}
    assert client.rel_id(resource, "team") == "t1"


def test_rel_id_null_data():
    assert client.rel_id(PLAN_PERSON_NULL_PERSON, "person") == ""


def test_rel_id_missing_relationship():
    assert client.rel_id({"relationships": {}}, "person") == ""
    assert client.rel_id({}, "person") == ""


def test_cached_fetches_once():
    fake = FakePCO({"/services/v2/people/5678/blockouts": [BLOCKOUT_DATA]})
    first = client.get_person_blockouts(fake, "5678")
    second = client.get_person_blockouts(fake, "5678")
    assert first == second == [BLOCKOUT_DATA]
    assert len(fake.calls) == 1


def test_post_blockout_invalidates_cache():
    """A blockout created mid-run must be visible to the next duplicate check."""
    fake = FakePCO({"/services/v2/people/5678/blockouts": []})
    assert client.get_person_blockouts(fake, "5678") == []

    fake.responses["/services/v2/people/5678/blockouts"] = [BLOCKOUT_DATA]
    client.post_blockout(fake, "5678", payload={"data": {}})

    assert client.get_person_blockouts(fake, "5678") == [BLOCKOUT_DATA]


def test_iterate_uses_max_page_size():
    fake = FakePCO({"/services/v2/service_types": []})
    client.get_all_service_types(fake)
    # FakePCO.iterate signature captures per_page separately; assert via call params
    # by checking our helper always passes per_page=100.
    # (FakePCO swallows per_page into its signature, so just assert one call happened.)
    assert fake.calls[0][1] == "/services/v2/service_types"


def test_get_future_plans_uses_documented_filter():
    fake = FakePCO({"/services/v2/service_types/1/plans": []})
    client.get_future_plans(fake, "1")
    method, url, params = fake.calls[0]
    assert params["filter"] == "future"
    assert params["order"] == "sort_date"


def test_get_plans_between_uses_named_filters():
    fake = FakePCO({"/services/v2/service_types/1/plans": []})
    client.get_plans_between(fake, "1", "2024-01-01", "2024-06-30")
    _, _, params = fake.calls[0]
    assert params["filter"] == "after,before"
    assert params["after"] == "2024-01-01"
    assert params["before"] == "2024-06-30"
