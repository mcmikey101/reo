import logging
from datetime import timedelta
from uuid import UUID, uuid4

import httpx
from sqlalchemy import func, select, update

from app.clients.ml import SENTIMENT_TIMEOUT
from app.config import get_settings
from app.db import get_sessionmaker
from app.errors import NotFoundError
from app.models import Review, ReviewImport, ReviewSentiment
from app.schemas.imports import (
    ImportAnalysis,
    ImportAnalysisError,
    ImportAnalysisResult,
    SentimentCounts,
)
from app.scope import OrgScope
from app.services.imports import select_import
from app.services.sentiment import analyze_import

logger = logging.getLogger(__name__)

# Пачка может ждать несколько попыток ML. Запас позволяет восстановить прерванный запуск.
RUN_LEASE = timedelta(minutes=15)


class AnalysisRunExpired(Exception):
    """Попытка больше не владеет запуском анализа."""


def get_import_analysis(scope: OrgScope, import_id: UUID) -> ImportAnalysis:
    report = _get_report(scope, import_id, for_start=False)
    return _analysis_status(scope, report)


def start_import_analysis(scope: OrgScope, import_id: UUID) -> tuple[ImportAnalysis, UUID | None]:
    report = _get_report(scope, import_id, for_start=True)
    analysis = _analysis_status(scope, report)
    if analysis.status in ("running", "done"):
        return analysis, None

    run_id = uuid4()
    report.analysis_run_id = run_id
    report.analysis_lease_until = scope.db.scalar(select(func.clock_timestamp())) + RUN_LEASE
    report.analysis_failed = False
    scope.db.commit()
    return ImportAnalysis(import_id=import_id, status="running"), run_id


def _get_report(scope: OrgScope, import_id: UUID, *, for_start: bool) -> ReviewImport:
    statement = select_import(scope, import_id).with_for_update(of=ReviewImport, read=not for_start)
    report = scope.db.scalar(statement)
    if report is None:
        raise NotFoundError("Импорт не найден")
    return report


def _analysis_status(scope: OrgScope, report: ReviewImport) -> ImportAnalysis:
    lease_until = report.analysis_lease_until
    if lease_until is not None and lease_until > scope.db.scalar(select(func.clock_timestamp())):
        return ImportAnalysis(import_id=report.id, status="running")

    done = ReviewSentiment.status == "done"
    total, finished, errors, positive, neutral, negative, avg_score = scope.db.execute(
        select(
            func.count(),
            func.count().filter(ReviewSentiment.status.in_(("done", "skipped"))),
            func.count().filter(ReviewSentiment.status == "error"),
            func.count().filter(done, ReviewSentiment.label == "positive"),
            func.count().filter(done, ReviewSentiment.label == "neutral"),
            func.count().filter(done, ReviewSentiment.label == "negative"),
            func.avg(ReviewSentiment.score).filter(done),
        )
        .select_from(Review)
        .outerjoin(ReviewSentiment, ReviewSentiment.review_id == Review.id)
        .where(Review.import_id == report.id)
    ).one()

    error = None
    if report.analysis_failed or lease_until is not None:
        error = ImportAnalysisError(code="analysis_failed", message="Не удалось завершить анализ")
    elif errors:
        error = ImportAnalysisError(
            code="ml_error", message="Не удалось обработать часть или все отзывы"
        )
    elif finished < total:
        return ImportAnalysis(import_id=report.id, status="pending")

    return ImportAnalysis(
        import_id=report.id,
        status="error" if error else "done",
        result=ImportAnalysisResult(
            sentiment_counts=SentimentCounts(positive=positive, neutral=neutral, negative=negative),
            satisfaction_index=50 * (1 + avg_score) if avg_score is not None else None,
        ),
        error=error,
    )


def run_import_analysis(organization_id: UUID, import_id: UUID, run_id: UUID) -> None:
    with get_sessionmaker()() as db:
        scope = OrgScope(db, organization_id)
        owned_run = update(ReviewImport).where(
            ReviewImport.id == import_id, ReviewImport.analysis_run_id == run_id
        )

        def renew_run() -> None:
            renewed = db.scalar(
                owned_run.where(ReviewImport.analysis_lease_until > func.clock_timestamp())
                .values(analysis_lease_until=func.clock_timestamp() + RUN_LEASE)
                .returning(ReviewImport.id)
            )
            if renewed is None:
                raise AnalysisRunExpired

        failed = False
        try:
            with httpx.Client(
                base_url=get_settings().ml_url, timeout=SENTIMENT_TIMEOUT, trust_env=False
            ) as client:
                analyze_import(scope, import_id, client, renew_run=renew_run)
        except (NotFoundError, AnalysisRunExpired):
            return
        except Exception:
            logger.exception("Импорт %s: не удалось завершить анализ", import_id)
            failed = True

        with db.begin():
            db.execute(
                owned_run.values(
                    analysis_run_id=None, analysis_lease_until=None, analysis_failed=failed
                )
            )
