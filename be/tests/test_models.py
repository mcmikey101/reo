"""Схема моделей без подключения к БД: таблицы, связи с организацией, ограничения полей."""

import pytest
from sqlalchemy import Table

from app.models import Base

TABLES = Base.metadata.tables


def test_tables_exist() -> None:
    assert set(TABLES) == {
        "organizations",
        "users",
        "points",
        "sources",
        "review_imports",
        "review_sentiments",
        "reviews",
    }


@pytest.mark.parametrize("name", list(TABLES))
def test_common_columns(name: str) -> None:
    table = TABLES[name]
    (key,) = table.primary_key.columns
    if name == "review_sentiments":
        assert key.name == "review_id"
        (fk,) = key.foreign_keys
        assert fk.target_fullname == "reviews.id"
        assert fk.ondelete == "CASCADE"
    else:
        assert key.name == "id"
        assert str(key.server_default.arg) == "gen_random_uuid()"
    for column in ("created_at", "updated_at"):
        assert table.c[column].type.timezone is True
        assert table.c[column].nullable is False


@pytest.mark.parametrize("name", ["users", "points"])
def test_bound_to_organization(name: str) -> None:
    table: Table = TABLES[name]
    column = table.c.organization_id
    assert column.nullable is False
    assert column.index is True
    (fk,) = column.foreign_keys
    assert fk.target_fullname == "organizations.id"
    assert fk.ondelete == "CASCADE"


def test_point_fields_match_form_limits() -> None:
    # Лимиты формы точки из docs/screens.md (M1)
    points = TABLES["points"]
    assert (points.c.name.type.length, points.c.name.nullable) == (120, False)
    assert (points.c.address.type.length, points.c.address.nullable) == (250, False)
    assert (points.c.category.type.length, points.c.category.nullable) == (60, True)


def test_user_email_unique_case_insensitive() -> None:
    users = TABLES["users"]
    (index,) = [index for index in users.indexes if index.name == "uq_users_email_lower"]
    assert index.unique is True
    assert str(index.expressions[0]) == "lower(users.email)"
