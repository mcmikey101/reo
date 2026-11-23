"""Проверка CSV целиком до записи в БД. Правила — docs/data-rules.md."""

import csv
import hashlib
import io
import json
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.errors import AppError
from app.schemas.imports import CsvRowError

MAX_CSV_BYTES = 10 * 1024 * 1024
HEADER = ["date", "text", "rating"]
RATING_MESSAGE = "Оценка должна быть числом от 1 до 5 или пустой"
SYNTAX_MESSAGE = "Нарушен синтаксис CSV: проверьте кавычки"
# csv.reader даже в строгом режиме допускает кавычки в необрамлённом поле.
CSV_FIELD = r'(?:"(?:[^"]++|"")*+"|[^",\r\n]*+)'
CSV_RECORD = re.compile(rf"{CSV_FIELD}(?:,{CSV_FIELD})*+(?:\r\n|[\r\n])?")
# Стандартный лимит csv (128 КиБ) меньше допустимого текста в файле.
csv.field_size_limit(max(csv.field_size_limit(), MAX_CSV_BYTES))


class InvalidCsvError(AppError):
    status_code = 422
    code = "invalid_csv"

    def __init__(self, message: str, row: int | None = None):
        super().__init__(message, {"row": row})


class CsvTooLargeError(AppError):
    status_code = 413
    code = "file_too_large"
    message = "Размер CSV не должен превышать 10 МиБ"

    def __init__(self):
        super().__init__(details={"max_bytes": MAX_CSV_BYTES})


@dataclass(frozen=True)
class CsvReview:
    date: date
    text: str
    rating: float | None

    @property
    def dedup_key(self) -> str:
        payload = json.dumps(
            [self.date.isoformat(), self.text, self.rating],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass
class ParsedCsv:
    reviews: list[CsvReview]
    errors: list[CsvRowError]

    @property
    def total(self) -> int:
        return len(self.reviews) + len(self.errors)


def parse_csv(content: bytes) -> ParsedCsv:
    if len(content) > MAX_CSV_BYTES:
        raise CsvTooLargeError()
    try:
        decoded = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise InvalidCsvError("Файл должен быть в кодировке UTF-8") from exc

    stream = io.StringIO(decoded, newline="")
    reader = csv.reader(stream, strict=True)
    row_number = 1
    parsed = ParsedCsv(reviews=[], errors=[])
    try:
        header = next(reader, None)
        if header != HEADER:
            raise InvalidCsvError("Заголовок должен быть date,text,rating", row=1)
        while True:
            row_number = reader.line_num + 1
            start = stream.tell()
            row = next(reader, None)
            if row is None:
                break
            if CSV_RECORD.fullmatch(decoded, start, stream.tell()) is None:
                raise InvalidCsvError(SYNTAX_MESSAGE, row=row_number)
            if not row:
                continue
            result = _parse_row(row, row_number)
            if isinstance(result, CsvRowError):
                parsed.errors.append(result)
            else:
                parsed.reviews.append(result)
    except csv.Error as exc:
        raise InvalidCsvError(SYNTAX_MESSAGE, row=row_number) from exc
    return parsed


def _parse_row(row: list[str], number: int) -> CsvReview | CsvRowError:
    def error(field: str | None, code: str, message: str) -> CsvRowError:
        return CsvRowError(row=number, field=field, code=code, message=message)

    if len(row) != 3:
        return error(None, "invalid_columns", "В записи должно быть три колонки: date,text,rating")

    raw_date, text, raw_rating = (value.strip() for value in row)
    try:
        if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", raw_date):
            raise ValueError
        review_date = date.fromisoformat(raw_date)
    except ValueError:
        return error("date", "invalid_date", "Дата должна быть существующей датой YYYY-MM-DD")

    if not text:
        return error("text", "blank", "Текст отзыва обязателен")
    if "\x00" in text:
        return error("text", "invalid_text", "Текст не должен содержать символ NUL")
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    rating = None
    if raw_rating:
        if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", raw_rating):
            return error("rating", "invalid_rating", RATING_MESSAGE)
        numeric_rating = Decimal(raw_rating)
        if not 1 <= numeric_rating <= 5:
            return error("rating", "invalid_rating", RATING_MESSAGE)
        rating = float(numeric_rating)

    return CsvReview(date=review_date, text=text, rating=rating)
