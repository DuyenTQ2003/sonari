"""GET /v1/speaking-items over HTTP with the database replaced: shape, contract, error envelope.
tests/integration/test_speaking_items_api_live.py runs it against the real MongoDB."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from fakes import AppFactory
from sonari_core.content.router import ItemOut, load_items

SCHEMA = json.loads(
    (
        Path(__file__).resolve().parents[3]
        / "packages/contracts/schema/speaking-items-response.schema.json"
    ).read_text("utf-8")
)
ITEMS = [
    ItemOut(id="voa:1@voa-trim/aaaaaaaaaaaa#0:0", text="The students read the book.", unit="Study"),
    ItemOut(id="voa:2@voa-trim/aaaaaaaaaaaa#3:5", text="Is there easy information?", unit="Study"),
]


def client_with(make_app: AppFactory, items: list[ItemOut]) -> TestClient:
    app = make_app()
    app.dependency_overrides[load_items] = lambda: items
    return TestClient(app, raise_server_exceptions=False)


def test_it_lists_the_items_in_the_order_the_store_gives_them(make_app: AppFactory) -> None:
    response = client_with(make_app, ITEMS).get("/v1/speaking-items")

    assert response.status_code == 200
    assert response.json() == {"items": [item.model_dump() for item in ITEMS]}


def test_the_response_matches_the_contract(make_app: AppFactory) -> None:
    body = client_with(make_app, ITEMS).get("/v1/speaking-items").json()

    Draft202012Validator(SCHEMA).validate(body)


def test_no_items_is_an_empty_list_not_an_error(make_app: AppFactory) -> None:
    response = client_with(make_app, []).get("/v1/speaking-items")

    assert (response.status_code, response.json()) == (200, {"items": []})


def test_it_is_read_only(make_app: AppFactory) -> None:
    response = client_with(make_app, ITEMS).post("/v1/speaking-items", json={})

    assert response.status_code == 405
    assert response.json()["error"]["messageKey"] == "errors.method_not_allowed"


def test_a_failing_store_comes_back_as_the_error_envelope(make_app: AppFactory) -> None:
    def broken() -> list[ItemOut]:
        raise RuntimeError("mongo is down")

    app = make_app()
    app.dependency_overrides[load_items] = broken

    response = TestClient(app, raise_server_exceptions=False).get("/v1/speaking-items")

    assert response.status_code == 500
    assert response.json() == {
        "error": {"code": "internal_error", "messageKey": "errors.internal", "details": None}
    }


@pytest.mark.parametrize("field", ["id", "text", "unit"])
def test_the_contract_requires_every_field(field: str) -> None:
    item = ITEMS[0].model_dump()
    del item[field]

    errors = list(Draft202012Validator(SCHEMA).iter_errors({"items": [item]}))

    assert len(errors) == 1
