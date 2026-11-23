"""Общие фикстуры тестов API без скачивания весов модели."""

import importlib
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Тесты запускаются как из ml/, так и командой pytest из корня репозитория.
ML_ROOT = Path(__file__).resolve().parents[1]
if str(ML_ROOT) not in sys.path:
    sys.path.insert(0, str(ML_ROOT))

api_main = importlib.import_module("api.main")
sentiment_model = importlib.import_module("sentiment.model")
app = api_main.app
Probabilities = sentiment_model.Probabilities


class StubSentimentModel:
    version = "mock-0.1"
    mock = True

    def predict(self, texts: list[str]) -> list[Probabilities]:
        return [Probabilities(pos=0.2, neu=0.6, neg=0.2) for _ in texts]


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr("api.main.load_sentiment_model", StubSentimentModel)
    with TestClient(app) as test_client:
        yield test_client
