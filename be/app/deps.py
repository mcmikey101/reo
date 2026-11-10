"""Общие зависимости FastAPI: текущий пользователь и доступ к данным его организации.

Роутеры берут данные только через Scope (и CurrentUser, если нужен сам пользователь)
и не передают organization_id вручную. Поэтому реальный вход в E10 меняет только
get_current_user: остальной код не знает, откуда взялся пользователь.
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.scope import OrgScope
from app.seed import DEMO_USER_ID

DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(db: DbSession) -> User:
    """Заглушка до E10: всегда демо-пользователь из seed (app/seed.py).

    В E10 здесь появится проверка входа, а при её отсутствии — ответ 401.
    """
    user = db.get(User, DEMO_USER_ID)
    if user is None:
        # Ошибка развёртывания, а не запроса: без seed-данных API работать не может
        raise RuntimeError("Демо-пользователь не найден в БД: выполните python -m app.seed")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_scope(user: CurrentUser, db: DbSession) -> OrgScope:
    """Доступ к данным организации текущего пользователя. Сессия — та же, что у запроса."""
    return OrgScope(db, user.organization_id)


Scope = Annotated[OrgScope, Depends(get_scope)]
