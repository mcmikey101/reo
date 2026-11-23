from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


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


class SentimentCounts(BaseModel):
    positive: int = Field(ge=0)
    neutral: int = Field(ge=0)
    negative: int = Field(ge=0)


class ImportAnalysisResult(BaseModel):
    sentiment_counts: SentimentCounts
    satisfaction_index: float | None = Field(ge=0, le=100)


class ImportAnalysisError(BaseModel):
    code: Literal["ml_error", "analysis_failed"]
    message: str


class ImportAnalysis(BaseModel):
    import_id: UUID
    status: Literal["pending", "running", "done", "error"]
    result: ImportAnalysisResult | None = None
    error: ImportAnalysisError | None = None
