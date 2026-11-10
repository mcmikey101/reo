"""Демо-данные до E10: две организации с точками и по пользователю в каждой.

Запуск из папки be/: python -m app.seed (контейнер api делает это при старте после миграций).
Скрипт идемпотентный: записи с фиксированными id вставляются, только если их ещё нет.
Повторный запуск ничего не дублирует и не перезаписывает изменённые записи.

Организация A — демо-организация: её пользователь подставляется заглушкой get_current_user
(app/deps.py). Организация B нужна, чтобы проверять изоляцию: её данные A не видит.
"""

import logging
import uuid
from typing import Any

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db import get_sessionmaker
from app.models import Base, Organization, Point, User

logger = logging.getLogger(__name__)

# Организация A и пользователь заглушки
DEMO_ORG_ID = uuid.UUID("a0000000-0000-4000-8000-000000000001")
DEMO_USER_ID = uuid.UUID("a0000000-0000-4000-8000-000000000101")
# Организация B — «чужая» для демо-пользователя
OTHER_ORG_ID = uuid.UUID("b0000000-0000-4000-8000-000000000001")
OTHER_USER_ID = uuid.UUID("b0000000-0000-4000-8000-000000000101")

ORGANIZATIONS = [
    {"id": DEMO_ORG_ID, "name": "Кофейня «Зерно»", "industry": "Общепит"},
    {"id": OTHER_ORG_ID, "name": "Клиника «Пульс»", "industry": "Медицина"},
]

USERS = [
    {"id": DEMO_USER_ID, "organization_id": DEMO_ORG_ID, "email": "demo@reo.local", "name": "Демо"},
    {
        "id": OTHER_USER_ID,
        "organization_id": OTHER_ORG_ID,
        "email": "other@reo.local",
        "name": "Другая организация",
    },
]

POINTS = [
    {
        "id": uuid.UUID("a0000000-0000-4000-8000-000000000201"),
        "organization_id": DEMO_ORG_ID,
        "name": "Зерно на Тверской",
        "address": "Москва, ул. Тверская, 1",
        "category": "кофейня",
    },
    {
        "id": uuid.UUID("a0000000-0000-4000-8000-000000000202"),
        "organization_id": DEMO_ORG_ID,
        "name": "Зерно на Арбате",
        "address": "Москва, ул. Арбат, 24",
        "category": "кофейня",
    },
    {
        "id": uuid.UUID("a0000000-0000-4000-8000-000000000203"),
        "organization_id": DEMO_ORG_ID,
        "name": "Зерно в Сокольниках",
        "address": "Москва, ул. Русаковская, 31",
        "category": None,
    },
    {
        "id": uuid.UUID("b0000000-0000-4000-8000-000000000201"),
        "organization_id": OTHER_ORG_ID,
        "name": "Пульс на Ленинском",
        "address": "Москва, Ленинский пр-т, 52",
        "category": "клиника",
    },
    {
        "id": uuid.UUID("b0000000-0000-4000-8000-000000000202"),
        "organization_id": OTHER_ORG_ID,
        "name": "Пульс на Мира",
        "address": "Москва, пр-т Мира, 79",
        "category": "клиника",
    },
]


def _insert_missing(session: Session, model: type[Base], rows: list[dict[str, Any]]) -> int:
    # Без указания конфликта пропускаются и занятые id, и занятый email пользователя.
    # RETURNING отдаёт только вставленные строки: так считаем, сколько добавлено
    statement = insert(model).values(rows).on_conflict_do_nothing().returning(model.id)
    return len(session.execute(statement).all())


def seed(session: Session) -> dict[str, int]:
    """Добавляет недостающие демо-записи. Возвращает, сколько записей каждой таблицы вставлено.

    Не коммитит: транзакцией управляет вызывающий.
    """
    return {
        "organizations": _insert_missing(session, Organization, ORGANIZATIONS),
        "users": _insert_missing(session, User, USERS),
        "points": _insert_missing(session, Point, POINTS),
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s [%(name)s] %(message)s")
    with get_sessionmaker()() as session, session.begin():
        inserted = seed(session)
    logger.info("Seed: добавлено %s", inserted)


if __name__ == "__main__":
    main()
