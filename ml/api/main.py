"""reo ML-сервис: точка входа FastAPI.

Реализует часть контракта backend <-> ML v0.2 (docs/ml-contract.md):
GET /health, GET /v1/health и POST /v1/sentiment.

Корень импортов — папка ml/. Запуск из ml/:
    uvicorn api.main:app --host 0.0.0.0 --port 8001
"""

import asyncio
import logging
import math
from collections import Counter
from contextlib import asynccontextmanager, suppress
from typing import Any, Literal, Protocol

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator, model_validator
from starlette.exceptions import HTTPException as StarletteHTTPException

from sentiment.model import HuggingFaceSentimentModel, Probabilities

logger = logging.getLogger("reo_ml")

MAX_BATCH = 256
MAX_TEXT_CHARS = 10_000
RATING_MIN, RATING_MAX = 1, 5

Label = Literal["negative", "neutral", "positive"]


# ---------------------------------------------------------------------------
# Схемы запросов и ответов (раздел 3 контракта)
# ---------------------------------------------------------------------------


class ReviewIn(BaseModel):
    id: str = Field(min_length=1)
    text: str | None
    # Диапазон 1–5 проверяется в analyze(): оценка вне диапазона пропускает
    # только этот отзыв (skipped, invalid_rating), а не всю пачку
    rating: float | None

    @field_validator("text")
    @classmethod
    def truncate_text(cls, value: str | None) -> str | None:
        return value[:MAX_TEXT_CHARS] if value is not None else None


class SentimentRequest(BaseModel):
    reviews: list[ReviewIn] = Field(min_length=1, max_length=MAX_BATCH)

    @model_validator(mode="after")
    def unique_ids(self) -> "SentimentRequest":
        counts = Counter(r.id for r in self.reviews)
        duplicates = sorted(review_id for review_id, n in counts.items() if n > 1)
        if duplicates:
            raise ValueError(f"id отзывов в пачке должны быть уникальны, повторяются: {duplicates}")
        return self


class Probs(BaseModel):
    pos: float
    neu: float
    neg: float


class SentimentResult(BaseModel):
    id: str
    status: Literal["ok", "skipped"]
    reason: str | None = None
    method: Literal["model", "rating"] | None = None
    label: Label | None = None
    probs: Probs | None = None
    score: float | None = None


class SentimentResponse(BaseModel):
    model_version: str
    results: list[SentimentResult]


class HealthResponse(BaseModel):
    status: Literal["ok", "loading"]
    models: dict[str, str]
    mock: bool


# Ошибки в формате контракта: {"error": {"code", "message", "details"}}


class ServiceError(Exception):
    def __init__(self, http_status: int, code: str, message: str, details: Any = None):
        super().__init__(message)
        self.http_status = http_status
        self.code = code
        self.message = message
        self.details = details


def error_response(http_status: int, code: str, message: str, details: Any = None) -> JSONResponse:
    return JSONResponse(
        status_code=http_status,
        content={"error": {"code": code, "message": message, "details": details}},
    )


# ---------------------------------------------------------------------------
# Модели тональности
# ---------------------------------------------------------------------------


class SentimentModel(Protocol):
    """Интерфейс модели: принимает тексты и возвращает вероятности классов."""

    version: str

    mock: bool

    def predict(self, texts: list[str]) -> list[Probabilities]: ...


def label_from_rating(rating: float) -> Label:
    # 1–2 → негатив, 3 → нейтрально, 4–5 → позитив
    if rating <= 2:
        return "negative"
    if rating < 4:
        return "neutral"
    return "positive"


HARD_PROBS: dict[Label, Probs] = {
    "positive": Probs(pos=1.0, neu=0.0, neg=0.0),
    "neutral": Probs(pos=0.0, neu=1.0, neg=0.0),
    "negative": Probs(pos=0.0, neu=0.0, neg=1.0),
}


# ---------------------------------------------------------------------------
# Логика эндпоинта: правила раздела 3 контракта, общие для заглушки и модели
# ---------------------------------------------------------------------------


def has_text(review: ReviewIn) -> bool:
    return bool(review.text and review.text.strip())


def build_result(
    review_id: str, method: Literal["model", "rating"], probs: Probs
) -> SentimentResult:
    scores: dict[Label, float] = {
        "positive": probs.pos,
        "neutral": probs.neu,
        "negative": probs.neg,
    }
    label = max(scores, key=scores.__getitem__)
    return SentimentResult(
        id=review_id,
        status="ok",
        method=method,
        label=label,
        probs=probs,
        score=round(probs.pos - probs.neg, 4),
    )


def has_valid_rating(review: ReviewIn) -> bool:
    rating = review.rating
    return rating is None or (math.isfinite(rating) and RATING_MIN <= rating <= RATING_MAX)


def analyze(reviews: list[ReviewIn], model: SentimentModel) -> list[SentimentResult]:
    """Оценка вне 1–5 → skipped; есть текст → модель; нет текста, есть оценка → звёзды;
    нет ничего → skipped."""
    results: list[SentimentResult | None] = [None] * len(reviews)
    text_indices: list[int] = []

    for i, review in enumerate(reviews):
        if not has_valid_rating(review):
            results[i] = SentimentResult(id=review.id, status="skipped", reason="invalid_rating")
        elif has_text(review):
            text_indices.append(i)
        elif review.rating is not None:
            label = label_from_rating(review.rating)
            results[i] = build_result(review.id, "rating", HARD_PROBS[label])
        else:
            results[i] = SentimentResult(id=review.id, status="skipped", reason="no_text_no_rating")

    if text_indices:
        # В модель уходит одна пачка с текстами, порядок результатов сохраняется
        probabilities = model.predict([reviews[i].text or "" for i in text_indices])
        for i, p in zip(text_indices, probabilities, strict=True):
            probs = Probs(pos=p.pos, neu=p.neu, neg=p.neg)
            results[i] = build_result(reviews[i].id, "model", probs)

    return [r for r in results if r is not None]


# ---------------------------------------------------------------------------
# Приложение
# ---------------------------------------------------------------------------


async def initialize_sentiment(app: FastAPI) -> None:
    try:
        model = await asyncio.to_thread(load_sentiment_model)
    except Exception:
        app.state.sentiment_load_failed = True
        logger.exception("Не удалось загрузить модель тональности")
        return

    app.state.sentiment = model
    logger.info("Модель тональности загружена: %s", model.version)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.sentiment = None
    app.state.sentiment_load_failed = False
    loading = asyncio.create_task(initialize_sentiment(app))
    try:
        yield
    finally:
        loading.cancel()
        with suppress(asyncio.CancelledError):
            await loading
        app.state.sentiment = None


app = FastAPI(title="reo ML", version="0.1.0", lifespan=lifespan)


def load_sentiment_model() -> SentimentModel:
    return HuggingFaceSentimentModel.from_pretrained()


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    codes = {404: "not_found", 405: "method_not_allowed"}
    code = codes.get(exc.status_code, "http_error")
    message = exc.detail if isinstance(exc.detail, str) else "HTTP-ошибка"
    return error_response(exc.status_code, code, message, None)


@app.exception_handler(ServiceError)
async def service_error_handler(request: Request, exc: ServiceError) -> JSONResponse:
    return error_response(exc.http_status, exc.code, exc.message, exc.details)


@app.get("/health")
def health_simple() -> dict[str, str]:
    return {"status": "ok"}


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = [
        {"field": ".".join(str(part) for part in e["loc"][1:]), "message": e["msg"]}
        for e in exc.errors()
    ]
    first = errors[0] if errors else {"field": "", "message": "invalid request"}
    # Ошибка уровня всего тела (например, повтор id) приходит без поля
    message = f"{first['field']}: {first['message']}" if first["field"] else first["message"]
    return error_response(422, "invalid_request", message, {"errors": errors})


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Необработанная ошибка в %s", request.url.path)
    return error_response(500, "internal_error", "Внутренняя ошибка ML-сервиса")


def loaded_model(request: Request) -> SentimentModel | None:
    if getattr(request.app.state, "sentiment_load_failed", False):
        raise ServiceError(500, "internal_error", "Не удалось загрузить модель тональности")
    return getattr(request.app.state, "sentiment", None)


def get_model(request: Request) -> SentimentModel:
    model = loaded_model(request)
    if model is None:
        raise ServiceError(503, "model_not_ready", "Модель ещё загружается, повторите позже")
    return model


@app.get("/v1/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse | JSONResponse:
    model = loaded_model(request)
    if model is None:
        body = HealthResponse(status="loading", models={}, mock=False)
        return JSONResponse(status_code=503, content=body.model_dump())
    return HealthResponse(status="ok", models={"sentiment": model.version}, mock=model.mock)


@app.post("/v1/sentiment", response_model=SentimentResponse)
def sentiment(body: SentimentRequest, request: Request) -> SentimentResponse:
    model = get_model(request)
    return SentimentResponse(model_version=model.version, results=analyze(body.reviews, model))
