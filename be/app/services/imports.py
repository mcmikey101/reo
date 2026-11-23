"""Сохранение CSV и выборка новых отзывов загрузки для будущего конвейера анализа."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert

from app.errors import NotFoundError
from app.models import Point, Review, ReviewImport, Source
from app.schemas.imports import CsvImportResult
from app.scope import OrgScope
from app.services.csv_parser import parse_csv

INSERT_BATCH_SIZE = 500


def import_csv(scope: OrgScope, point_id: UUID, content: bytes) -> CsvImportResult:
    scope.get(Point, point_id, message="Точка не найдена")
    parsed = parse_csv(content)
    try:
        # Пока разбирался CSV, точку могли удалить. Повторная проверка удерживает её до commit.
        locked_point_id = scope.db.scalar(
            scope.select(Point)
            .with_only_columns(Point.id)
            .where(Point.id == point_id)
            .with_for_update(read=True, key_share=True, of=Point)
        )
        if locked_point_id is None:
            raise NotFoundError("Точка не найдена")

        # Уникальность источника и отзывов обеспечивает PostgreSQL, включая гонки запросов.
        scope.db.execute(
            insert(Source)
            .values(point_id=point_id, kind="csv", name="Импорт CSV")
            .on_conflict_do_nothing(
                index_elements=[Source.point_id],
                # Общему плану нужен литерал для сопоставления с частичным индексом.
                index_where=text("kind = 'csv'"),
            )
        )
        source = scope.db.scalars(
            select(Source).where(Source.point_id == point_id, Source.kind == "csv")
        ).one()
        report = ReviewImport(
            source_id=source.id,
            total=parsed.total,
            imported=0,
            duplicates=len(parsed.reviews),
            rejected=len(parsed.errors),
            errors=[error.model_dump() for error in parsed.errors],
        )
        scope.db.add(report)
        scope.db.flush()

        imported = 0
        for start in range(0, len(parsed.reviews), INSERT_BATCH_SIZE):
            values = [
                {
                    "source_id": source.id,
                    "import_id": report.id,
                    "date": review.date,
                    "text": review.text,
                    "rating": review.rating,
                    "dedup_key": review.dedup_key,
                }
                for review in parsed.reviews[start : start + INSERT_BATCH_SIZE]
            ]
            statement = (
                insert(Review)
                .values(values)
                .on_conflict_do_nothing(index_elements=[Review.source_id, Review.dedup_key])
                .returning(Review.id)
            )
            imported += len(scope.db.scalars(statement).all())

        report.imported = imported
        report.duplicates = len(parsed.reviews) - imported
        if imported:
            source.last_collected_at = datetime.now(UTC)
        result = CsvImportResult(
            import_id=report.id,
            point_id=point_id,
            source_id=source.id,
            total=report.total,
            imported=report.imported,
            duplicates=report.duplicates,
            rejected=report.rejected,
            errors=parsed.errors,
        )
        scope.db.commit()
        return result
    except Exception:
        scope.db.rollback()
        raise


def get_import_reviews(scope: OrgScope, import_id: UUID) -> list[Review]:
    """Только новые отзывы импорта своей организации; чужой и отсутствующий — 404."""
    report = scope.db.scalar(
        select(ReviewImport)
        .join(Source, Source.id == ReviewImport.source_id)
        .join(Point, Point.id == Source.point_id)
        .where(ReviewImport.id == import_id, Point.organization_id == scope.organization_id)
    )
    if report is None:
        raise NotFoundError("Импорт не найден")
    return list(
        scope.db.scalars(
            select(Review).where(Review.import_id == report.id).order_by(Review.date, Review.id)
        )
    )
