from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_serializer, with_config
from pydantic_core import PydanticCustomError
from typing_extensions import TypedDict

PointSort = Literal["name", "-name", "created_at", "-created_at"]
DataStatus = Literal["no_sources", "collecting", "ok", "error", "paused"]


def _trim(value: object) -> object:
    if not isinstance(value, str):
        return value
    if "\x00" in value or any("\ud800" <= char <= "\udfff" for char in value):
        raise PydanticCustomError("invalid_value", "Строка содержит недопустимый символ")
    return value.strip()


def _required_text(value: object) -> object:
    if value is None:
        raise PydanticCustomError("missing", "Обязательное поле")
    value = _trim(value)
    if value == "":
        raise PydanticCustomError("blank", "Заполните поле")
    return value


def _optional_text(value: object) -> object:
    value = _trim(value)
    return None if value == "" else value


PointName = Annotated[str, Field(min_length=1, max_length=120), BeforeValidator(_required_text)]
PointAddress = Annotated[str, Field(min_length=1, max_length=250), BeforeValidator(_required_text)]
PointCategory = Annotated[
    Annotated[str, Field(min_length=1, max_length=60)] | None, BeforeValidator(_optional_text)
]


class PointCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: PointName
    address: PointAddress
    category: PointCategory = None


@with_config(ConfigDict(extra="forbid"))
class PointUpdate(TypedDict, total=False):
    name: PointName
    address: PointAddress
    category: PointCategory


class PointListParams(BaseModel):
    q: Annotated[str, Field(max_length=100), BeforeValidator(_trim)] | None = None
    sort: PointSort = "name"
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


class PointOut(BaseModel):
    id: UUID
    name: str = Field(min_length=1, max_length=120)
    address: str = Field(min_length=1, max_length=250)
    category: str | None = Field(min_length=1, max_length=60)
    sources_count: int = Field(ge=0)
    data_status: DataStatus
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_at", "updated_at", when_used="json")
    def _as_utc(self, value: datetime) -> datetime:
        return value.astimezone(UTC)


class PointList(BaseModel):
    items: list[PointOut]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=200)
    offset: int = Field(ge=0)
