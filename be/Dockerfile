FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY pyproject.toml .
COPY app ./app

EXPOSE 8000

# Применение миграций при старте добавится в REO-24
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
