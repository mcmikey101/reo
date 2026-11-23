"""HTTP-контракт клиента тональности и поведение при сбоях ML."""

import json
from uuid import uuid4

import httpx
import pytest

from app.clients import ml


@pytest.mark.parametrize(
    ("status", "error_code", "expected_delays"),
    [(422, "ml_http_422", []), (503, "ml_http_503", [1, 4, 16])],
)
def test_http_retries(monkeypatch, status, error_code, expected_delays):
    delays = []
    requests = []
    monkeypatch.setattr(ml, "sleep", delays.append)
    review = ml.SentimentReview(uuid4(), "Вкусный кофе", None)

    def handle(request):
        requests.append(request)
        return httpx.Response(status)

    with httpx.Client(base_url="http://ml:8001", transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(ml.SentimentError, match=error_code):
            ml.get_sentiment(client, [review])

    assert delays == expected_delays
    assert len(requests) == len(delays) + 1
    for request in requests:
        assert (request.method, request.url.path) == ("POST", "/v1/sentiment")
        assert json.loads(request.content) == {
            "reviews": [{"id": str(review.id), "text": "Вкусный кофе", "rating": None}]
        }


def test_timeout_then_skipped_review(monkeypatch):
    delays = []
    monkeypatch.setattr(ml, "sleep", delays.append)
    review = ml.SentimentReview(uuid4(), None, None)

    def handle(request):
        if not delays:
            raise httpx.ReadTimeout("ML не ответил", request=request)
        return httpx.Response(
            200,
            json={
                "model_version": "mock-1",
                "results": [
                    {
                        "id": str(review.id),
                        "status": "skipped",
                        "reason": "no_text_no_rating",
                        "method": None,
                        "label": None,
                        "probs": None,
                        "score": None,
                    }
                ],
            },
        )

    with httpx.Client(base_url="http://ml:8001", transport=httpx.MockTransport(handle)) as client:
        response = ml.get_sentiment(client, [review])

    assert delays == [1]
    assert response.results[0].reason == "no_text_no_rating"


@pytest.mark.parametrize("problem", ["non_json", "duplicate_id", "unknown_id", "missing_score"])
def test_invalid_success_response_is_rejected(problem):
    reviews = [ml.SentimentReview(uuid4(), "Кофе", 5.0) for _ in range(2)]

    def handle(_):
        if problem == "non_json":
            return httpx.Response(200, text="broken")
        results = [
            {
                "id": str(review.id),
                "status": "ok",
                "reason": None,
                "method": "model",
                "label": "positive",
                "probs": {"pos": 0.8, "neu": 0.1, "neg": 0.1},
                "score": 0.7,
            }
            for review in reviews
        ]
        if problem == "duplicate_id":
            results[1]["id"] = results[0]["id"]
        elif problem == "unknown_id":
            results[1]["id"] = str(uuid4())
        else:
            del results[1]["score"]
        return httpx.Response(200, json={"model_version": "mock-1", "results": results})

    with httpx.Client(base_url="http://ml:8001", transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(ml.SentimentError, match="ml_invalid_response"):
            ml.get_sentiment(client, reviews)
