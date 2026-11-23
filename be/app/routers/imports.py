import asyncio
from concurrent.futures import Future, ThreadPoolExecutor
from threading import BoundedSemaphore
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, File, Form, Response, UploadFile

from app.deps import Scope
from app.schemas.imports import CsvImportResult, ImportAnalysis
from app.services.csv_parser import MAX_CSV_BYTES
from app.services.import_analysis import (
    get_import_analysis,
    run_import_analysis,
    start_import_analysis,
)
from app.services.imports import import_csv
from app.services.sentiment import ImportSentimentSummary

router = APIRouter(prefix="/imports", tags=["imports"])

ANALYSIS_WORKERS = 4
_analysis_executor = ThreadPoolExecutor(max_workers=ANALYSIS_WORKERS, thread_name_prefix="analysis")
_analysis_slots = BoundedSemaphore(ANALYSIS_WORKERS)


async def _wait_for_analysis(job: Future[ImportSentimentSummary | None]) -> None:
    await asyncio.wrap_future(job)


@router.post("/csv", response_model=CsvImportResult, status_code=201)
def create_csv_import(
    scope: Scope,
    point_id: Annotated[UUID, Form()],
    file: Annotated[UploadFile, File()],
) -> CsvImportResult:
    """Сохранить корректные отзывы из CSV; вернуть итог и ошибки отдельных записей."""
    return import_csv(scope, point_id, file.file.read(MAX_CSV_BYTES + 1))


@router.post(
    "/{import_id}/analysis",
    response_model=ImportAnalysis,
    responses={
        202: {"model": ImportAnalysis, "description": "Анализ выполняется"},
        503: {"description": "Все обработчики анализа заняты"},
    },
)
def start_analysis(
    import_id: UUID, scope: Scope, background_tasks: BackgroundTasks, response: Response
) -> ImportAnalysis:
    slot_reserved = _analysis_slots.acquire(blocking=False)
    try:
        analysis, run_id = start_import_analysis(scope, import_id, allow_start=slot_reserved)
        if run_id is not None:
            job = _analysis_executor.submit(
                run_import_analysis, scope.organization_id, import_id, run_id
            )
            job.add_done_callback(lambda _: _analysis_slots.release())
            slot_reserved = False
            background_tasks.add_task(_wait_for_analysis, job)
    finally:
        if slot_reserved:
            _analysis_slots.release()
    if analysis.status == "running":
        response.status_code = 202
    return analysis


@router.get("/{import_id}/analysis", response_model=ImportAnalysis)
def get_analysis(import_id: UUID, scope: Scope) -> ImportAnalysis:
    return get_import_analysis(scope, import_id)
