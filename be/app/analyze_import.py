"""Запуск анализа CSV-импорта: python -m app.analyze_import <import_id>."""

import argparse
import logging
import sys
from uuid import UUID

from app.db import get_sessionmaker
from app.deps import get_current_user
from app.errors import NotFoundError
from app.scope import OrgScope
from app.services.import_analysis import run_import_analysis, start_import_analysis
from app.services.sentiment import get_import_sentiment_summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Проанализировать отзывы CSV-импорта")
    parser.add_argument("import_id", type=UUID, help="UUID из ответа POST /imports/csv")
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(message)s")

    with get_sessionmaker()() as db:
        # Используем того же пользователя, что и API. Сейчас это пользователь из seed.
        scope = OrgScope(db, get_current_user(db).organization_id)
        try:
            analysis, run_id = start_import_analysis(scope, args.import_id)
        except NotFoundError as exc:
            print(exc.message, file=sys.stderr)
            return 1

        if analysis.status == "done":
            summary = get_import_sentiment_summary(scope, args.import_id)
        elif run_id is None:
            print("Анализ этого импорта уже выполняется", file=sys.stderr)
            return 1
        else:
            summary = run_import_analysis(scope.organization_id, args.import_id, run_id)

    if summary is None:
        print("Не удалось завершить анализ", file=sys.stderr)
        return 1

    print(
        f"Импорт {args.import_id}: done={summary.done}, "
        f"skipped={summary.skipped}, error={summary.error}"
    )
    return int(summary.error > 0)


if __name__ == "__main__":
    raise SystemExit(main())
