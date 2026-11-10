"""Правила POST /v1/sentiment из раздела 3 docs/ml-contract.md."""

import pytest
from fastapi.testclient import TestClient

from api.main import MAX_BATCH, MAX_TEXT_CHARS, ReviewIn, app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def post(client: TestClient, reviews: list[dict]) -> dict:
    response = client.post("/v1/sentiment", json={"reviews": reviews})
    assert response.status_code == 200, response.text
    return response.json()


def test_contract_example(client: TestClient) -> None:
    body = post(
        client,
        [
            {"id": "r1", "text": "Кофе отличный, но заказ ждали 40 минут", "rating": 3},
            {"id": "r2", "text": None, "rating": 5},
            {"id": "r3", "text": "", "rating": None},
        ],
    )

    assert body["model_version"] == "mock-0.1"
    r1, r2, r3 = body["results"]
    assert [r["id"] for r in body["results"]] == ["r1", "r2", "r3"]

    assert r1["status"] == "ok"
    assert r1["method"] == "model"
    assert sum(r1["probs"].values()) == pytest.approx(1.0)
    assert r1["score"] == pytest.approx(r1["probs"]["pos"] - r1["probs"]["neg"])

    assert r2 == {
        "id": "r2",
        "status": "ok",
        "reason": None,
        "method": "rating",
        "label": "positive",
        "probs": {"pos": 1.0, "neu": 0.0, "neg": 0.0},
        "score": 1.0,
    }

    assert r3 == {
        "id": "r3",
        "status": "skipped",
        "reason": "no_text_no_rating",
        "method": None,
        "label": None,
        "probs": None,
        "score": None,
    }


@pytest.mark.parametrize(
    ("rating", "label", "score"),
    [
        (1, "negative", -1.0),
        (2, "negative", -1.0),
        (3, "neutral", 0.0),
        (4, "positive", 1.0),
        (5, "positive", 1.0),
    ],
)
def test_no_text_uses_rating(client: TestClient, rating: int, label: str, score: float) -> None:
    (result,) = post(client, [{"id": "a", "text": "   ", "rating": rating}])["results"]

    assert result["method"] == "rating"
    assert result["label"] == label
    assert result["score"] == score


@pytest.mark.parametrize("rating", [0, 6, -1, 10])
def test_invalid_rating_skips_only_that_review(client: TestClient, rating: int) -> None:
    results = post(
        client,
        [
            {"id": "a", "text": "Всё хорошо", "rating": 5},
            {"id": "b", "text": "Всё хорошо", "rating": rating},
            {"id": "c", "text": None, "rating": 4},
        ],
    )["results"]

    assert [r["status"] for r in results] == ["ok", "skipped", "ok"]
    assert results[1]["reason"] == "invalid_rating"


def test_order_is_preserved_for_mixed_batch(client: TestClient) -> None:
    reviews = [
        {"id": str(i), "text": "текст" if i % 2 else None, "rating": (i % 5) + 1}
        for i in range(MAX_BATCH)
    ]
    results = post(client, reviews)["results"]

    assert [r["id"] for r in results] == [r["id"] for r in reviews]


def test_repeated_call_gives_same_answer(client: TestClient) -> None:
    reviews = [
        {"id": "a", "text": "Долго ждали", "rating": 2},
        {"id": "b", "text": None, "rating": 4},
    ]

    assert post(client, reviews) == post(client, reviews)


def test_long_text_is_truncated() -> None:
    review = ReviewIn(id="a", text="x" * (MAX_TEXT_CHARS + 500), rating=None)

    assert len(review.text) == MAX_TEXT_CHARS


@pytest.mark.parametrize(
    ("reviews", "field"),
    [
        ([], "reviews"),
        ([{"id": str(i), "text": "x", "rating": None} for i in range(MAX_BATCH + 1)], "reviews"),
        ([{"id": "a", "rating": 5}], "reviews.0.text"),
        ([{"id": "", "text": "x", "rating": None}], "reviews.0.id"),
        ([{"id": "a", "text": "x", "rating": "много"}], "reviews.0.rating"),
    ],
)
def test_invalid_request_is_422(client: TestClient, reviews: list[dict], field: str) -> None:
    response = client.post("/v1/sentiment", json={"reviews": reviews})

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "invalid_request"
    assert error["details"]["errors"][0]["field"] == field


def test_duplicate_ids_are_422(client: TestClient) -> None:
    reviews = [{"id": "a", "text": None, "rating": 1}, {"id": "a", "text": None, "rating": 5}]
    response = client.post("/v1/sentiment", json={"reviews": reviews})

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "invalid_request"
    assert "['a']" in error["message"]


def test_v1_health_reports_mock_model(client: TestClient) -> None:
    response = client.get("/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "models": {"sentiment": "mock-0.1"}, "mock": True}
