"""Пограничные случаи формата CSV без обращения к БД."""

from datetime import date

import pytest

from app.services.csv_parser import (
    MAX_CSV_BYTES,
    CsvTooLargeError,
    InvalidCsvError,
    parse_csv,
)


def csv(row: str) -> bytes:
    return f"date,text,rating\n{row}\n".encode()


def test_bom_crlf_quotes_multiline_and_physical_row_numbers() -> None:
    content = (
        '\ufeffdate,text,rating\r\n2026-11-20,"Кофе, вкусный\r\nи ""свежий""",4.5\r\n'
        "\r\n2026-11-21,   ,5\r\n2026-11-22,Без оценки,\r\n"
    ).encode()

    parsed = parse_csv(content)

    assert parsed.total == 3
    assert [(r.date, r.text, r.rating) for r in parsed.reviews] == [
        (date(2026, 11, 20), 'Кофе, вкусный\nи "свежий"', 4.5),
        (date(2026, 11, 22), "Без оценки", None),
    ]
    assert [(e.row, e.field, e.code) for e in parsed.errors] == [(5, "text", "blank")]


@pytest.mark.parametrize(
    ("row", "field", "code"),
    [
        ("2026-11-20,Текст", None, "invalid_columns"),
        ("2026-11-20,Текст,5,лишнее", None, "invalid_columns"),
        (",Текст,5", "date", "invalid_date"),
        ("2026-02-29,Текст,5", "date", "invalid_date"),
        ("20261120,Текст,5", "date", "invalid_date"),
        ("2026-1-20,Текст,5", "date", "invalid_date"),
        ("20.11.2026,Текст,5", "date", "invalid_date"),
        ("2026-11-20T12:00:00,Текст,5", "date", "invalid_date"),
        ("2026-11-20, ,5", "text", "blank"),
        ("2026-11-20,Текст\x00,5", "text", "invalid_text"),
        ("2026-11-20,Текст,0", "rating", "invalid_rating"),
        ("2026-11-20,Текст,6", "rating", "invalid_rating"),
        ("2026-11-20,Текст,5.00000000000000000001", "rating", "invalid_rating"),
        ("2026-11-20,Текст,0.99999999999999999999", "rating", "invalid_rating"),
        ("2026-11-20,Текст,NaN", "rating", "invalid_rating"),
        ("2026-11-20,Текст,inf", "rating", "invalid_rating"),
        ("2026-11-20,Текст,пять", "rating", "invalid_rating"),
        ('2026-11-20,Текст,"4,5"', "rating", "invalid_rating"),
        (",,", "date", "invalid_date"),
    ],
)
def test_invalid_record_does_not_discard_valid_record(
    row: str, field: str | None, code: str
) -> None:
    parsed = parse_csv(csv(f"{row}\n2026-11-22,Корректная запись,1"))

    assert parsed.total == 2
    assert len(parsed.reviews) == len(parsed.errors) == 1
    assert parsed.reviews[0].text == "Корректная запись"
    assert parsed.errors[0].model_dump() == {
        "row": 2,
        "field": field,
        "code": code,
        "message": parsed.errors[0].message,
    }
    assert parsed.errors[0].message


@pytest.mark.parametrize(
    "content",
    [
        b"",
        b"\xef\xbb\xbf",
        b"date;text;rating\n",
        b"text,date,rating\n",
        b"date,text\n",
        b"date,text,rating,author\n",
        "date,text,rating\n2026-11-20,Отзыв,5".encode("cp1251"),
        csv('2026-11-20,Хороший отзыв,5\n2026-11-21,"Незакрытые кавычки,5'),
        csv('2026-11-20,"Лишнее"после кавычек,5'),
    ],
)
def test_file_errors(content: bytes) -> None:
    with pytest.raises(InvalidCsvError):
        parse_csv(content)


@pytest.mark.parametrize("text", ['"Не закрыто\nи продолжение', 'Кавычки "без обрамления"'])
def test_syntax_error_reports_first_line_of_invalid_record(text: str) -> None:
    with pytest.raises(InvalidCsvError) as exc:
        parse_csv(csv(f'2026-11-20,"Норма\nи продолжение",5\n2026-11-21,{text},5'))
    assert exc.value.details == {"row": 4}


def test_header_only_is_empty_import() -> None:
    assert parse_csv(b"date,text,rating\n\n").total == 0


def test_normalization_gives_same_duplicate_key() -> None:
    first = parse_csv(csv(" 2026-11-20 , Текст ,5")).reviews[0]
    second = parse_csv(csv("2026-11-20,Текст,5.0")).reviews[0]

    assert first.dedup_key == second.dedup_key
    assert len(first.dedup_key) == 64
    assert first.dedup_key != parse_csv(csv("2026-11-20,Текст,")).reviews[0].dedup_key


def test_long_text_is_kept_without_csv_default_field_limit() -> None:
    text = "я" * 200_000
    assert parse_csv(csv(f"2026-11-20,{text},5")).reviews[0].text == text


def test_file_size_limit_is_in_bytes_and_inclusive() -> None:
    prefix = b"date,text,rating\n2026-11-20,"
    content = prefix + b"a" * (MAX_CSV_BYTES - len(prefix) - 2) + b",5"
    assert len(content) == MAX_CSV_BYTES
    assert len(parse_csv(content).reviews) == 1

    with pytest.raises(CsvTooLargeError):
        parse_csv(content + b"\n")
