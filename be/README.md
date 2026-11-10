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
│   ├── deps.py          # общие зависимости FastAPI: get_current_user, Scope
│   ├── scope.py         # OrgScope — доступ к данным организации текущего пользователя
│   ├── errors.py        # ошибки приложения (NotFoundError…) и их ответы по контракту
│   ├── seed.py          # демо-данные: python -m app.seed
│   ├── routers/         # HTTP-слой: эндпоинты, без бизнес-логики
│   ├── schemas/         # Pydantic-схемы запросов и ответов
│   ├── services/        # бизнес-логика: что делает эндпоинт
│   ├── models/          # модели SQLAlchemy — таблицы БД; base.py — Base и общие поля
│   └── clients/         # клиенты внешних сервисов: ML-сервис, площадки отзывов
├── alembic/             # миграции БД: env.py, versions/
├── alembic.ini          # настройки Alembic
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
| `models/` | Таблицы SQLAlchemy по [../docs/db-schema.md](../docs/db-schema.md): наследуют `Base`, `UUIDPrimaryKeyMixin`, `TimestampMixin`; каждая таблица с данными организации связана с `organizations`. Новую модель импортируем в `models/__init__.py` | Pydantic-схемы |
| `clients/` | Исходящие HTTP-вызовы: `ml.py` — ML-сервис по `docs/ml-contract.md`, парсеры площадок | Работу с БД |
| `alembic/` | Миграции. Схема меняется только новой миграцией (см. [«Миграции»](#миграции)) | Правки уже влитых миграций |
| `tests/` | `test_<фича>.py`, общие фикстуры — в `conftest.py` | — |

### Как добавить новую фичу

Для фичи заводим файлы с одним именем в каждом слое. Пример для точек:

```
app/routers/points.py    # router = APIRouter(prefix="/points", tags=["points"])
app/schemas/points.py    # PointCreate, PointUpdate, PointOut
app/services/points.py   # list_points(scope), create_point(scope, ...)
app/models/point.py      # class Point(Base)
tests/test_points.py
```

Роутер подключаем в `app/main.py`: `app.include_router(points.router)`.

### Данные организации: `Scope`

Все запросы к данным фильтруются по организации текущего пользователя. Фильтр не пишем вручную: эндпоинт получает зависимость `Scope` из `app/deps.py` и передаёт её в сервис, а сервис работает с данными через `OrgScope` (`app/scope.py`):

```python
# routers/points.py
@router.get("/{point_id}", response_model=PointOut)
def get_point(point_id: UUID, scope: Scope):
    return points_service.get_point(scope, point_id)


# services/points.py
def get_point(scope: OrgScope, point_id: UUID) -> Point:
    return scope.get(Point, point_id, message="Точка не найдена")  # чужая или нет → 404


def list_points(scope: OrgScope) -> list[Point]:
    return list(scope.db.scalars(scope.select(Point).order_by(Point.name)))


def create_point(scope: OrgScope, data: PointCreate) -> Point:
    point = scope.add(Point(**data.model_dump()))  # organization_id ставит scope
    scope.db.commit()
    return point
```

| Метод | Что делает |
|---|---|
| `scope.select(Model)` | `select(Model)` с условием по организации, дальше — свои `where`, `order_by` |
| `scope.get(Model, id)` | Запись своей организации, иначе `NotFoundError` → `404 not_found` (чужая запись для API не существует) |
| `scope.add(obj)` | Ставит `organization_id` и добавляет запись в сессию |
| `scope.db` | Сессия запроса: commit, delete и запросы к таблицам без своего `organization_id` |

- `organization_id` не берём из запроса и не отдаём в ответе ([api-contract.md](../docs/api-contract.md#12-организация-и-доступ)).
- У таблиц, связанных с организацией через родителя (отзыв → точка), своего `organization_id` нет, и `scope.select(Review)` бросит `TypeError`. Такие таблицы фильтруем join'ом с родителем: `select(Review).join(Point).where(Point.organization_id == scope.organization_id)`.
- Сервисы бросают ошибки из `app/errors.py` (`NotFoundError`), а не `HTTPException`: ответ в формате контракта собирает общий обработчик.

## Seed и текущий пользователь

До входа (E10) текущего пользователя подставляет заглушка `get_current_user` в `app/deps.py`: это всегда демо-пользователь `demo@reo.local` организации «Кофейня «Зерно»». Данные создаёт скрипт:

```bash
python -m app.seed
```

| Организация | Пользователь | Точки | Зачем |
|---|---|---|---|
| Кофейня «Зерно» | `demo@reo.local` — текущий пользователь | 3 | Демо |
| Клиника «Пульс» | `other@reo.local` | 2 | Проверка изоляции: её данные демо-пользователь не видит |

- Скрипт идемпотентный: id записей фиксированы (`app/seed.py`), повторный запуск ничего не дублирует и не перезаписывает изменённые записи.
- Контейнер `api` запускает его при старте после миграций.
- Если демо-пользователя нет в БД, запросы с `Scope` падают с 500 и подсказкой запустить seed.
- В E10 меняется только `get_current_user`: вместо демо-пользователя — пользователь из входа, при его отсутствии — 401. Остальной код получает пользователя через `CurrentUser` и `Scope` и не меняется.

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
alembic upgrade head
python -m app.seed
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

Контейнер при старте выполняет `alembic upgrade head` и `python -m app.seed`, затем запускает uvicorn. Если БД недоступна или один из шагов упал, контейнер завершается с ошибкой (fail fast): API не работает на устаревшей схеме.

## Миграции

Схема и соглашения — [../docs/db-schema.md](../docs/db-schema.md). Alembic берёт строку подключения из `DATABASE_URL`. Команды — из папки `be/`:

```bash
alembic upgrade head                                  # применить все миграции
alembic downgrade -1                                  # откатить последнюю
alembic current                                       # текущая версия БД
alembic heads                                         # головы: в main всегда одна
alembic revision --autogenerate -m "add sources"      # новая миграция по изменённым моделям
```

Порядок изменения схемы:

1. Изменить или добавить модель в `app/models/`, новую — импортировать в `app/models/__init__.py`.
2. `alembic revision --autogenerate -m "…"` — файл появится в `alembic/versions/` с датой в имени и отформатируется ruff.
3. Проверить файл руками: autogenerate не видит расширения, данные, переименования колонок и таблиц.
4. `alembic upgrade head`, `alembic downgrade -1`, снова `alembic upgrade head` на локальной БД.
5. Обновить `docs/db-schema.md` в том же PR, пометить Сергея, Михаила и Камиля.

Влитую в `main` миграцию не редактируем — только новая миграция.

### Тесты миграций

`tests/test_migrations.py` применяет и откатывает миграции на настоящем PostgreSQL + pgvector и проверяет, что модели совпадают с миграциями. `tests/test_org_scope.py` на той же БД проверяет seed и изоляцию организаций; каждый тест работает в транзакции, которая откатывается. Без `TEST_DATABASE_URL` эти тесты пропускаются. Нужна **отдельная** БД — тесты удаляют все таблицы:

```bash
docker run -d --name reo-db-test -e POSTGRES_PASSWORD=reo -e POSTGRES_DB=reo_test -p 55432:5432 pgvector/pgvector:pg16
export TEST_DATABASE_URL=postgresql://postgres:reo@localhost:55432/reo_test   # PowerShell: $env:TEST_DATABASE_URL="..."
pytest
docker rm -f reo-db-test
```
