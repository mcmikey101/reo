from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Form, UploadFile

from app.deps import Scope
from app.schemas.imports import CsvImportResult
from app.services.csv_parser import MAX_CSV_BYTES
from app.services.imports import import_csv

router = APIRouter(prefix="/imports", tags=["imports"])


@router.post("/csv", response_model=CsvImportResult, status_code=201)
def create_csv_import(
    scope: Scope,
    point_id: Annotated[UUID, Form()],
    file: Annotated[UploadFile, File()],
) -> CsvImportResult:
    """Сохранить корректные отзывы из CSV; вернуть итог и ошибки отдельных записей."""
    return import_csv(scope, point_id, file.file.read(MAX_CSV_BYTES + 1))
