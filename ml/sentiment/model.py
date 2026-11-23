"""Загрузка и инференс выбранной модели тональности."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

_REQUIRED_LABELS = {"negative", "neutral", "positive"}
_DEFAULT_CONFIG = Path(__file__).with_name("config.yaml")


@dataclass(frozen=True)
class SentimentModelConfig:
    model_id: str
    revision: str
    device: str
    max_tokens: int
    inference_batch_size: int

    @property
    def version(self) -> str:
        return f"{self.model_id}@{self.revision[:8]}"

    @classmethod
    def load(cls, path: Path = _DEFAULT_CONFIG) -> SentimentModelConfig:
        with path.open(encoding="utf-8") as config_file:
            data = yaml.safe_load(config_file)

        if not isinstance(data, dict):
            raise ValueError(f"Некорректный конфиг модели: {path}")

        model_id = data.get("model_id")
        revision = data.get("revision")
        device = data.get("device", "cpu")
        max_tokens = data.get("max_tokens", 512)
        inference_batch_size = data.get("inference_batch_size", 32)

        if not isinstance(model_id, str) or not model_id.strip():
            raise ValueError("В конфиге модели должен быть задан непустой model_id")
        if not isinstance(revision, str) or not revision.strip():
            raise ValueError("В конфиге модели должна быть задана ревизия")
        if not isinstance(device, str) or not device.strip():
            raise ValueError("В конфиге модели должно быть задано устройство")
        if isinstance(max_tokens, bool) or not isinstance(max_tokens, int) or max_tokens < 1:
            raise ValueError("max_tokens должен быть положительным целым числом")
        if (
            isinstance(inference_batch_size, bool)
            or not isinstance(inference_batch_size, int)
            or inference_batch_size < 1
        ):
            raise ValueError("inference_batch_size должен быть положительным целым числом")

        return cls(
            model_id=model_id,
            revision=revision,
            device=device,
            max_tokens=max_tokens,
            inference_batch_size=inference_batch_size,
        )


@dataclass(frozen=True)
class Probabilities:
    pos: float
    neu: float
    neg: float


class HuggingFaceSentimentModel:
    """Классификатор тональности, параметры которого берутся из YAML-конфига."""

    mock = False

    def __init__(
        self,
        config: SentimentModelConfig,
        tokenizer: Any,
        model: Any,
    ) -> None:
        import torch

        self._torch = torch
        self._config = config
        self.version = config.version
        self._tokenizer = tokenizer
        self._model = model.to(config.device)
        self._model.eval()
        self._device = config.device

        id2label = {
            int(index): str(label).lower() for index, label in self._model.config.id2label.items()
        }
        if set(id2label.values()) != _REQUIRED_LABELS:
            raise ValueError(
                "Ожидались метки negative, neutral, positive; "
                f"модель вернула {sorted(id2label.values())}"
            )
        self._label_indices = {label: index for index, label in id2label.items()}

    @classmethod
    def from_pretrained(cls, config_path: Path = _DEFAULT_CONFIG) -> HuggingFaceSentimentModel:
        """Загружает модель и токенизатор по настройкам из config.yaml."""
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        config = SentimentModelConfig.load(config_path)
        tokenizer = AutoTokenizer.from_pretrained(
            config.model_id,
            revision=config.revision,
        )
        model = AutoModelForSequenceClassification.from_pretrained(
            config.model_id,
            revision=config.revision,
        )
        return cls(config=config, tokenizer=tokenizer, model=model)

    def predict(self, texts: list[str]) -> list[Probabilities]:
        if not texts:
            return []

        outputs: list[Probabilities] = []
        batch_size = self._config.inference_batch_size
        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            encoded = self._tokenizer(
                batch,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=self._config.max_tokens,
            )
            encoded = {key: value.to(self._device) for key, value in encoded.items()}
            with self._torch.inference_mode():
                logits = self._model(**encoded).logits
                probabilities = self._torch.softmax(logits, dim=-1).cpu().tolist()

            for row in probabilities:
                outputs.append(
                    Probabilities(
                        pos=float(row[self._label_indices["positive"]]),
                        neu=float(row[self._label_indices["neutral"]]),
                        neg=float(row[self._label_indices["negative"]]),
                    )
                )
        return outputs
