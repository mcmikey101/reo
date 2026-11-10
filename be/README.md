# be — бэкенд API

API reo: Python 3.11, FastAPI, SQLAlchemy 2 (драйвер psycopg 3), Alembic, PostgreSQL 16 + pgvector.

Отвечают:
- Сергей Косарев — то, что **читает и отдаёт** данные фронту: каркас API, точки, дашборд, отзывы, выгрузки;
- Михаил Подъельников — то, что **записывает** данные в БД: инфраструктура, источники (парсинг и CSV), конвейер к ML-сервису, фоновые задачи.

- Порт: 8000.
- Единственная часть, которая работает с БД и вызывает ML-сервис.
- Зависимости — `requirements.txt` (рантайм, pytest и ruff), линтер — ruff.
- Dockerfile бэкенда лежит в этой папке.

Соглашения — в [../docs/conventions.md](../docs/conventions.md).

## Структура

Структуру задаёт Сергей, Михаил следует ей. Изменения структуры — через PR с пометкой для обоих.

```
be/
├── app/
│   ├── main.py          # создание приложения: CORS, подключение роутеров
│   ├── config.py        # настройки из переменных окружения (Settings)
│   ├── db.py            # engine и сессии SQLAlchemy, зависимость get_db
│   ├── deps.py          # общие зависимости FastAPI, get_current_user (появится в REO-27)
│   ├── routers/         # HTTP-слой: эндпоинты, без бизнес-логики
│   ├── schemas/         # Pydantic-схемы запросов и ответов
│   ├── services/        # бизнес-логика: что делает эндпоинт
│   ├── models/          # модели SQLAlchemy — таблицы БД (REO-24)
│   └── clients/         # клиенты внешних сервисов: ML-сервис, площадки отзывов
├── alembic/             # миграции БД (появится в REO-24)
├── tests/               # тесты pytest
├── Dockerfile
├── pyproject.toml       # настройки ruff и pytest
└── requirements.txt
```

| Каталог | Что кладём | Чего не кладём |
|---|---|---|
| `routers/` | Эндпоинты: путь, метод, параметры, `response_model`, зависимости | Запросы к БД, вызовы ML, вычисления |
| `schemas/` | Pydantic-модели входа и выхода API. Это контракт для фронта, его видно в `/docs` | Модели SQLAlchemy |
| `services/` | Логика фичи: запросы к БД через сессию, вызовы `clients/`, расчёты | HTTP-детали (коды ответов, заголовки) |
| `models/` | Таблицы SQLAlchemy. Каждая таблица с данными организации связана с `organization` | Pydantic-схемы |
| `clients/` | Исходящие HTTP-вызовы: `ml.py` — ML-сервис по `docs/ml-contract.md`, парсеры площадок | Работу с БД |
| `alembic/` | Миграции. Схема меняется только новой миграцией | — |
| `tests/` | `test_<фича>.py`, общие фикстуры — в `conftest.py` | — |

### Как добавить новую фичу

Для фичи заводим файлы с одним именем в каждом слое. Пример для точек:

```
app/routers/points.py    # router = APIRouter(prefix="/points", tags=["points"])
app/schemas/points.py    # PointCreate, PointUpdate, PointOut
app/services/points.py   # list_points(db, org_id), create_point(...)
app/models/point.py      # class Point(Base)
tests/test_points.py
```

Роутер подключаем в `app/main.py`: `app.include_router(points.router)`.

Все запросы к данным фильтруются по организации текущего пользователя. Фильтр берём из общей зависимости в `app/deps.py` (REO-27), а не пишем вручную в каждом эндпоинте.

## Переменные окружения

| Переменная | Значение |
|---|---|
| `DATABASE_URL` | Строка подключения к PostgreSQL. Подходит `postgresql://user:pass@host:5432/db`: схема сама заменяется на `postgresql+psycopg://`. Хост `db` — внутри Docker Compose, `localhost` — при запуске вне Docker |
| `ML_URL` | Адрес ML-сервиса, по умолчанию `http://ml:8001` |

CORS разрешает `http://localhost:5173` (фронтенд).

## `GET /health`

```json
{"status": "ok", "db": "ok|error", "ml": "ok|error"}
```

- Всегда отвечает кодом 200: раз API ответил, он работает.
- `db` — результат `SELECT 1` в PostgreSQL.
- `ml` — результат `GET {ML_URL}/health`, ожидается `{"status": "ok"}`.
- Таймаут каждой проверки — 2 секунды, проверки идут параллельно.
- Если БД или ML недоступны, соответствующее поле становится `error`, эндпоинт не падает.

## Запуск

Локально, нужен Python 3.11:

```bash
cd be
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export DATABASE_URL=postgresql://user:pass@localhost:5432/reo   # Windows PowerShell: $env:DATABASE_URL="..."
export ML_URL=http://localhost:8001
uvicorn app.main:app --reload --port 8000
```

Swagger: http://localhost:8000/docs.

Проверки перед PR:

```bash
ruff check .
ruff format --check .
pytest
```

В Docker (весь проект поднимается через `docker-compose.yml` в корне — REO-18):

```bash
docker build -t reo-api be/
docker run --rm -p 8000:8000 -e DATABASE_URL=... -e ML_URL=... reo-api
```

Применение миграций при старте контейнера добавится в REO-24.
