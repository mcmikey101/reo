"""reo ML-сервис: точка входа FastAPI.

Реализует часть контракта backend <-> ML v0.1 (docs/contract_backend_ml.md):
GET /v1/health и POST /v1/sentiment.

Запуск: uvicorn ml.api.main:app --host 0.0.0.0 --port 8001
"""

import logging
from contextlib import asynccontextmanager
from typing import Annotated, Any, Literal, Protocol

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger("reo_ml")

MAX_BATCH = 256
MAX_TEXT_CHARS = 10_000

Label = Literal["negative", "neutral", "positive"]


# ---------------------------------------------------------------------------
# Схемы запросов и ответов (раздел 3 контракта)
# ---------------------------------------------------------------------------


class ReviewIn(BaseModel):
    id: str = Field(min_length=1)
    text: str | None
    rating: Annotated[float, Field(ge=1, le=5)] | None

    @field_validator("text")
    @classmethod
    def truncate_text(cls, value: str | None) -> str | None:
        return value[:MAX_TEXT_CHARS] if value is not None else None


class SentimentRequest(BaseModel):
    reviews: list[ReviewIn] = Field(min_length=1, max_length=MAX_BATCH)


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
    """Интерфейс модели: получает только отзывы с текстом, возвращает вероятности."""

    version: str

    def predict(self, reviews: list[ReviewIn]) -> list[Probs]: ...


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


class MockSentiment:
    """Заглушка модели: детерминированный ответ по звёздам.

    «Мягкие» вероятности нужны, чтобы ответ был похож на ответ настоящей модели.
    Отзыв с текстом, но без оценки, считается нейтральным.
    """

    version = "mock-0.1"

    _SOFT: dict[Label, Probs] = {
        "positive": Probs(pos=0.80, neu=0.15, neg=0.05),
        "neutral": Probs(pos=0.20, neu=0.60, neg=0.20),
        "negative": Probs(pos=0.05, neu=0.15, neg=0.80),
    }

    def predict(self, reviews: list[ReviewIn]) -> list[Probs]:
        return [
            self._SOFT[label_from_rating(r.rating) if r.rating is not None else "neutral"]
            for r in reviews
        ]


# ---------------------------------------------------------------------------
# Логика эндпоинта: правила раздела 3 контракта, общие для заглушки и модели
# ---------------------------------------------------------------------------


def has_text(review: ReviewIn) -> bool:
    return bool(review.text and review.text.strip())


def build_result(review_id: str, method: Literal["model", "rating"], probs: Probs) -> SentimentResult:
    scores: dict[Label, float] = {"positive": probs.pos, "neutral": probs.neu, "negative": probs.neg}
    label = max(scores, key=scores.__getitem__)
    return SentimentResult(
        id=review_id,
        status="ok",
        method=method,
        label=label,
        probs=probs,
        score=round(probs.pos - probs.neg, 4),
    )


def analyze(reviews: list[ReviewIn], model: SentimentModel) -> list[SentimentResult]:
    """Есть текст → модель; нет текста, есть оценка → звёзды; нет ничего → skipped."""
    results: list[SentimentResult | None] = [None] * len(reviews)
    text_indices: list[int] = []

    for i, review in enumerate(reviews):
        if has_text(review):
            text_indices.append(i)
        elif review.rating is not None:
            label = label_from_rating(review.rating)
            results[i] = build_result(review.id, "rating", HARD_PROBS[label])
        else:
            results[i] = SentimentResult(id=review.id, status="skipped", reason="no_text_no_rating")

    if text_indices:
        # В модель уходит одна пачка с текстами, порядок результатов сохраняется
        probs = model.predict([reviews[i] for i in text_indices])
        for i, p in zip(text_indices, probs, strict=True):
            results[i] = build_result(reviews[i].id, "model", p)

    return [r for r in results if r is not None]


# ---------------------------------------------------------------------------
# Приложение
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Здесь позже: compose конфиг Hydra и app.state.sentiment = instantiate(cfg.sentiment)
    app.state.sentiment = MockSentiment()
    app.state.mock = True
    logger.info("Модель тональности загружена: %s", app.state.sentiment.version)
    yield
    app.state.sentiment = None


app = FastAPI(title="reo ML", version="0.1.0", lifespan=lifespan)


@app.exception_handler(ServiceError)
async def service_error_handler(request: Request, exc: ServiceError) -> JSONResponse:
    return error_response(exc.http_status, exc.code, exc.message, exc.details)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = [
        {"field": ".".join(str(part) for part in e["loc"][1:]), "message": e["msg"]}
        for e in exc.errors()
    ]
    first = errors[0] if errors else {"field": "", "message": "invalid request"}
    return error_response(
        422, "invalid_request", f"{first['field']}: {first['message']}", {"errors": errors}
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Необработанная ошибка в %s", request.url.path)
    return error_response(500, "internal_error", "Внутренняя ошибка ML-сервиса")


def get_model(request: Request) -> SentimentModel:
    model = getattr(request.app.state, "sentiment", None)
    if model is None:
        raise ServiceError(503, "model_not_ready", "Модель ещё загружается, повторите позже")
    return model


@app.get("/v1/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse | JSONResponse:
    model = getattr(request.app.state, "sentiment", None)
    mock = getattr(request.app.state, "mock", False)
    if model is None:
        body = HealthResponse(status="loading", models={}, mock=mock)
        return JSONResponse(status_code=503, content=body.model_dump())
    return HealthResponse(status="ok", models={"sentiment": model.version}, mock=mock)


@app.post("/v1/sentiment", response_model=SentimentResponse)
def sentiment(body: SentimentRequest, request: Request) -> SentimentResponse:
    model = get_model(request)
    return SentimentResponse(model_version=model.version, results=analyze(body.reviews, model))