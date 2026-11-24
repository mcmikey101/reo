"""HTTP-клиент ML-сервиса. Контракт — docs/ml-contract.md."""

from dataclasses import dataclass
from time import sleep
from typing import Annotated, Literal
from uuid import UUID

import httpx
from pydantic import BaseModel, Field, ValidationError

from app.schemas.health import MlStatus

# ML пакует тексты по длине самого длинного, поэтому для CPU берём запас от лимита 256.
SENTIMENT_BATCH_SIZE = 32
SENTIMENT_PADDED_TEXT_BUDGET = 8_192
SENTIMENT_TEXT_LIMIT = 10_000
SENTIMENT_TIMEOUT = httpx.Timeout(60, connect=5)
SENTIMENT_SINGLE_TIMEOUT = httpx.Timeout(60, connect=5, read=120)
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
    def __init__(self, code: str, *, retryable: bool = False, split_batch: bool = False) -> None:
        super().__init__(code)
        self.code = code
        self.retryable = retryable
        self.split_batch = split_batch


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
    can_split = len(payload) > 1
    timeout = client.timeout if can_split else SENTIMENT_SINGLE_TIMEOUT
    try:
        response = client.post("/v1/sentiment", json={"reviews": payload}, timeout=timeout)
    except httpx.ReadTimeout as exc:
        raise SentimentError("ml_timeout", retryable=not can_split, split_batch=can_split) from exc
    except httpx.TimeoutException as exc:
        raise SentimentError("ml_timeout", retryable=True) from exc
    except httpx.RequestError as exc:
        raise SentimentError("ml_unavailable") from exc

    if response.status_code != 200:
        if can_split and response.status_code in (413, 504):
            raise SentimentError(f"ml_http_{response.status_code}", split_batch=True)
        raise SentimentError(f"ml_http_{response.status_code}", retryable=response.is_server_error)
    try:
        return SentimentResponse.model_validate_json(response.content, strict=True)
    except ValidationError as exc:
        raise SentimentError("ml_invalid_response") from exc


async def get_health(base_url: str, timeout: float) -> MlStatus:
    """Проверить готовность модели, включая штатную загрузку весов."""
    # ML — внутренний сервис: прокси из HTTP(S)_PROXY к нему не применяем
    async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
        response = await client.get(f"{base_url}/v1/health")
    if response.status_code not in (200, 503):
        return "error"
    body = response.json()
    status = body.get("status") if isinstance(body, dict) else None
    if response.status_code == 200 and status == "ok":
        return "ok"
    if response.status_code == 503 and status == "loading":
        return "loading"
    return "error"
