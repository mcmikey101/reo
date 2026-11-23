"""Анализ выбранного CSV-импорта вне запроса загрузки."""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

import httpx
from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert

from app.clients.ml import (
    SENTIMENT_BATCH_SIZE,
    SENTIMENT_PADDED_TEXT_BUDGET,
    SENTIMENT_TEXT_LIMIT,
    SentimentError,
    SentimentResponse,
    SentimentReview,
    get_sentiment,
)
from app.errors import NotFoundError
from app.models import Review, ReviewImport, ReviewSentiment
from app.scope import OrgScope
from app.services.imports import select_import

logger = logging.getLogger(__name__)
ResultRow = dict[str, UUID | str | float | datetime | None]


@dataclass(frozen=True)
class ImportSentimentSummary:
    done: int
    skipped: int
    error: int


def analyze_import(
    scope: OrgScope,
    import_id: UUID,
    client: httpx.Client,
    *,
    renew_run: Callable[[], None] | None = None,
) -> ImportSentimentSummary:
    """Обработать отзывы без результата и ошибки. Сервис управляет транзакциями сессии."""
    with scope.db.begin():
        _require_import(scope, import_id)

    after: UUID | None = None
    batch_size = SENTIMENT_BATCH_SIZE
    while True:
        with scope.db.begin():
            if renew_run is not None:
                renew_run()
            batch = _next_batch(scope, import_id, after, batch_size)
        if not batch:
            break
        # ML и паузы между попытками не держат соединение или блокировки БД.
        try:
            rows = _result_rows(get_sentiment(client, batch))
        except SentimentError as exc:
            if exc.split_batch:
                batch_size = len(batch) // 2
                logger.info(
                    "Импорт %s: ML (%s), уменьшаем пачку с %s до %s отзывов",
                    import_id,
                    exc.code,
                    len(batch),
                    batch_size,
                )
                continue
            logger.warning(
                "Импорт %s: ошибка ML (%s), отзывов в пачке: %s", import_id, exc.code, len(batch)
            )
            rows = [
                {"review_id": review.id, "status": "error", "reason": exc.code} for review in batch
            ]
        with scope.db.begin():
            if renew_run is not None:
                renew_run()
            # Импорт могли удалить во время запроса к ML. Защищаем запись до commit.
            _require_import(scope, import_id, lock=True)
            _save_results(scope, rows)
        # Ошибки этой пачки остаются в БД до следующего запуска команды.
        after = batch[-1].id

    with scope.db.begin():
        _require_import(scope, import_id)
        counts = dict(
            scope.db.execute(
                select(ReviewSentiment.status, func.count())
                .join(Review, Review.id == ReviewSentiment.review_id)
                .where(Review.import_id == import_id)
                .group_by(ReviewSentiment.status)
            ).all()
        )
    return ImportSentimentSummary(
        counts.get("done", 0), counts.get("skipped", 0), counts.get("error", 0)
    )


def _require_import(scope: OrgScope, import_id: UUID, *, lock: bool = False) -> None:
    statement = select_import(scope, import_id).with_only_columns(ReviewImport.id)
    if lock:
        statement = statement.with_for_update(read=True, key_share=True, of=ReviewImport)
    if scope.db.scalar(statement) is None:
        raise NotFoundError("Импорт не найден")


def _next_batch(
    scope: OrgScope, import_id: UUID, after: UUID | None, batch_size: int
) -> list[SentimentReview]:
    statement = (
        select(Review.id, func.left(Review.text, SENTIMENT_TEXT_LIMIT), Review.rating)
        .outerjoin(ReviewSentiment, ReviewSentiment.review_id == Review.id)
        .where(
            Review.import_id == import_id,
            or_(ReviewSentiment.review_id.is_(None), ReviewSentiment.status == "error"),
        )
        .order_by(Review.id)
        .limit(batch_size)
    )
    if after is not None:
        statement = statement.where(Review.id > after)

    batch: list[SentimentReview] = []
    longest_text = 0
    for row in scope.db.execute(statement).all():
        review = SentimentReview(*row)
        longest_text = max(longest_text, len(review.text or ""))
        # Длинный отзыв не должен увеличивать объём инференса всей пачки.
        if batch and longest_text * (len(batch) + 1) > SENTIMENT_PADDED_TEXT_BUDGET:
            break
        batch.append(review)
    return batch


def _result_rows(response: SentimentResponse) -> list[ResultRow]:
    analyzed_at = datetime.now(UTC)
    return [
        {
            "review_id": UUID(result.id),
            "status": "done" if result.status == "ok" else "skipped",
            "reason": result.reason,
            "method": result.method,
            "label": result.label,
            "p_pos": result.probs.pos if result.probs else None,
            "p_neu": result.probs.neu if result.probs else None,
            "p_neg": result.probs.neg if result.probs else None,
            "score": result.score,
            "model_version": response.model_version,
            "analyzed_at": analyzed_at,
        }
        for result in response.results
    ]


def _save_results(scope: OrgScope, rows: list[ResultRow]) -> None:
    # Одинаковый порядок записи при параллельных запусках, даже если ML переставил ответы.
    rows.sort(key=lambda row: str(row["review_id"]))
    statement = insert(ReviewSentiment).values(rows)
    changes = {key: statement.excluded[key] for key in rows[0] if key != "review_id"}
    scope.db.execute(
        statement.on_conflict_do_update(
            index_elements=[ReviewSentiment.review_id],
            set_=changes | {"updated_at": func.now()},
            where=ReviewSentiment.status == "error",
        )
    )
