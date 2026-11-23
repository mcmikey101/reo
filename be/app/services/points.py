from collections import Counter, defaultdict
from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, or_, select

from app.errors import PossibleDuplicateError
from app.models import Organization, Point, Source
from app.schemas.points import (
    DataStatus,
    PointCreate,
    PointList,
    PointListParams,
    PointOut,
    PointUpdate,
)
from app.scope import OrgScope


def list_points(scope: OrgScope, params: PointListParams) -> PointList:
    statement = scope.select(Point)
    if params.q:
        statement = statement.where(
            or_(
                Point.name.icontains(params.q, autoescape=True),
                Point.address.icontains(params.q, autoescape=True),
            )
        )

    total = scope.db.scalar(statement.with_only_columns(func.count())) or 0
    if params.offset >= total:
        return PointList(items=[], total=total, limit=params.limit, offset=params.offset)

    column = Point.created_at if params.sort.endswith("created_at") else Point.name
    order = column.desc() if params.sort.startswith("-") else column.asc()
    page = statement.order_by(order, Point.id).offset(params.offset).limit(params.limit)
    points = scope.db.scalars(page).all()
    return PointList(
        items=_outputs(scope, points), total=total, limit=params.limit, offset=params.offset
    )


def get_point(scope: OrgScope, point_id: UUID) -> PointOut:
    point = scope.get(Point, point_id, message="Точка не найдена")
    return _outputs(scope, [point])[0]


def create_point(scope: OrgScope, data: PointCreate, *, allow_duplicate: bool) -> PointOut:
    _lock_point_writes(scope)
    if not allow_duplicate:
        _check_duplicate(scope, data.name, data.address)
    point = scope.add(Point(name=data.name, address=data.address, category=data.category))
    scope.db.flush()
    result = _outputs(scope, [point])[0]
    scope.db.commit()
    return result


def update_point(
    scope: OrgScope, point_id: UUID, data: PointUpdate, *, allow_duplicate: bool
) -> PointOut:
    _lock_point_writes(scope)
    point = scope.get(Point, point_id, message="Точка не найдена")
    if data and not allow_duplicate:
        _check_duplicate(
            scope, data.get("name", point.name), data.get("address", point.address), point_id
        )
    for field, value in data.items():
        setattr(point, field, value)
    scope.db.flush()
    result = _outputs(scope, [point])[0]
    scope.db.commit()
    return result


def delete_point(scope: OrgScope, point_id: UUID) -> None:
    _lock_point_writes(scope)
    point = scope.get(Point, point_id, message="Точка не найдена")
    scope.db.delete(point)
    scope.db.commit()


def _lock_point_writes(scope: OrgScope) -> None:
    # Блокировка до конца транзакции не даёт двум запросам одновременно пройти проверку дубля.
    scope.db.execute(
        select(Organization.id)
        .where(Organization.id == scope.organization_id)
        .with_for_update(key_share=True)
    )


def _normalized(value: str) -> str:
    return " ".join(value.split()).casefold()


def _check_duplicate(
    scope: OrgScope, name: str, address: str, exclude_id: UUID | None = None
) -> None:
    candidates = scope.select(Point).with_only_columns(Point.id, Point.name, Point.address)
    if exclude_id is not None:
        candidates = candidates.where(Point.id != exclude_id)
    target = (_normalized(name), _normalized(address))
    for existing_id, existing_name, existing_address in scope.db.execute(
        candidates.order_by(Point.id)
    ):
        if (_normalized(existing_name), _normalized(existing_address)) == target:
            raise PossibleDuplicateError(
                details={
                    "existing_point": {
                        "id": str(existing_id),
                        "name": existing_name,
                        "address": existing_address,
                    }
                },
            )


def _outputs(scope: OrgScope, points: Sequence[Point]) -> list[PointOut]:
    if not points:
        return []
    counts: dict[UUID, Counter[str]] = defaultdict(Counter)
    statement = (
        select(Source.point_id, Source.status, func.count())
        .where(Source.point_id.in_([point.id for point in points]))
        .group_by(Source.point_id, Source.status)
    )
    for point_id, status, count in scope.db.execute(statement):
        counts[point_id][status] = count

    return [
        PointOut(
            id=point.id,
            name=point.name,
            address=point.address,
            category=point.category,
            sources_count=counts[point.id].total(),
            data_status=_data_status(counts[point.id]),
            created_at=point.created_at,
            updated_at=point.updated_at,
        )
        for point in points
    ]


def _data_status(counts: Counter[str]) -> DataStatus:
    if not counts:
        return "no_sources"
    if counts["error"]:
        return "error"
    if counts["checking"] or counts["collecting"]:
        return "collecting"
    if counts["ok"]:
        return "ok"
    return "paused"
