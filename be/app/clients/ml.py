"""HTTP-клиент ML-сервиса. Контракт — docs/ml-contract.md."""

from dataclasses import dataclass
from time import sleep
from typing import Annotated, Literal
from uuid import UUID

import httpx
from pydantic import BaseModel, Field, ValidationError

SENTIMENT_BATCH_SIZE = 256
SENTIMENT_TEXT_LIMIT = 10_000
SENTIMENT_TIMEOUT = httpx.Timeout(60, connect=5)
RETRY_DELAYS = (1, 4, 16)


@dataclass(frozen=True)
class SentimentReview:
    id: UUID
    text: str | None
    rating: float | None


Probability = Annotated[float, Field(ge=0, le=1)]


class Probabilities(BaseModel):
    pos: Probability
    neu: Probability
    neg: Probability


class SentimentDone(BaseModel):
    id: str
    status: Literal["ok"]
    reason: None
    method: Literal["model", "rating"]
    label: Literal["positive", "neutral", "negative"]
    probs: Probabilities
    score: Annotated[float, Field(ge=-1, le=1)]


class SentimentSkipped(BaseModel):
    id: str
    status: Literal["skipped"]
    reason: Literal["no_text_no_rating", "invalid_rating"]
    method: None
    label: None
    probs: None
    score: None


class SentimentResponse(BaseModel):
    model_version: str = Field(min_length=1, pattern=r"\S")
    results: list[Annotated[SentimentDone | SentimentSkipped, Field(discriminator="status")]]


class SentimentError(Exception):
    def __init__(self, code: str, *, retryable: bool = False) -> None:
        super().__init__(code)
        self.code = code
        self.retryable = retryable


def get_sentiment(client: httpx.Client, reviews: list[SentimentReview]) -> SentimentResponse:
    """Отправить пачку и проверить, что ML ответил ровно по переданным отзывам."""
    payload: list[dict[str, str | float | None]] = [
        {"id": str(review.id), "text": review.text, "rating": review.rating} for review in reviews
    ]
    for delay in RETRY_DELAYS:
        try:
            response = _post_sentiment(client, payload)
        except SentimentError as exc:
            if not exc.retryable:
                raise
            sleep(delay)
        else:
            break
    else:
        response = _post_sentiment(client, payload)

    expected_ids = {str(review.id) for review in reviews}
    result_ids = {result.id for result in response.results}
    if len(response.results) != len(reviews) or result_ids != expected_ids:
        raise SentimentError("ml_invalid_response")
    return response


def _post_sentiment(
    client: httpx.Client, payload: list[dict[str, str | float | None]]
) -> SentimentResponse:
    try:
        response = client.post("/v1/sentiment", json={"reviews": payload})
    except httpx.TimeoutException as exc:
        raise SentimentError("ml_timeout", retryable=True) from exc
    except httpx.RequestError as exc:
        raise SentimentError("ml_unavailable") from exc

    if response.status_code != 200:
        raise SentimentError(f"ml_http_{response.status_code}", retryable=response.is_server_error)
    try:
        return SentimentResponse.model_validate_json(response.content, strict=True)
    except ValidationError as exc:
        raise SentimentError("ml_invalid_response") from exc


async def get_health(base_url: str, timeout: float) -> bool:
    """True, если ML-сервис ответил 200 и {"status": "ok"}."""
    # ML — внутренний сервис: прокси из HTTP(S)_PROXY к нему не применяем
    async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
        response = await client.get(f"{base_url}/health")
    if response.status_code != 200:
        return False
    body = response.json()
    return isinstance(body, dict) and body.get("status") == "ok"
