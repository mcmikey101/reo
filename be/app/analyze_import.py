"""Запуск анализа CSV-импорта: python -m app.analyze_import <import_id>."""

import argparse
import logging
import sys
from uuid import UUID

import httpx

from app.clients.ml import SENTIMENT_TIMEOUT
from app.config import get_settings
from app.db import get_sessionmaker
from app.deps import get_current_user
from app.errors import NotFoundError
from app.scope import OrgScope
from app.services.sentiment import analyze_import


def main() -> int:
    parser = argparse.ArgumentParser(description="Проанализировать отзывы CSV-импорта")
    parser.add_argument("import_id", type=UUID, help="UUID из ответа POST /imports/csv")
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(message)s")

    with get_sessionmaker()() as db:
        # Используем того же пользователя, что и API. Сейчас это пользователь из seed.
        with db.begin():
            scope = OrgScope(db, get_current_user(db).organization_id)
        with httpx.Client(
            base_url=get_settings().ml_url, timeout=SENTIMENT_TIMEOUT, trust_env=False
        ) as client:
            try:
                summary = analyze_import(scope, args.import_id, client)
            except NotFoundError as exc:
                print(exc.message, file=sys.stderr)
                return 1

    print(
        f"Импорт {args.import_id}: done={summary.done}, "
        f"skipped={summary.skipped}, error={summary.error}"
    )
    return int(summary.error > 0)


if __name__ == "__main__":
    raise SystemExit(main())
