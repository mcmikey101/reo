from uuid import UUID

from pydantic import BaseModel


class CsvRowError(BaseModel):
    row: int
    field: str | None
    code: str
    message: str


class CsvImportResult(BaseModel):
    import_id: UUID
    point_id: UUID
    source_id: UUID
    total: int
    imported: int
    duplicates: int
    rejected: int
    errors: list[CsvRowError]
