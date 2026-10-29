"""Embedding providers. Fake vectors are for mechanics, not relevance evaluation."""
import hashlib
import math
import re
import time
from dataclasses import dataclass
from typing import Protocol

import httpx


class EmbeddingError(Exception):
    """Sanitized provider error; never include source text or credentials."""


@dataclass(frozen=True)
class EmbeddingBatch:
    vectors: list[list[float]]
    tokens: int
    estimated_cost_usd: float | None


class EmbeddingProvider(Protocol):
    provider: str
    model: str
    version: str
    dimensions: int
    def embed(self, inputs: list[str]) -> EmbeddingBatch: ...


def validate_vectors(vectors: list, count: int, dimensions: int) -> list[list[float]]:
    if len(vectors) != count or not 1 <= dimensions <= 2000:
        raise EmbeddingError("embedding_shape_invalid")
    result = []
    for vector in vectors:
        if not isinstance(vector, list) or len(vector) != dimensions:
            raise EmbeddingError("embedding_shape_invalid")
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in vector):
            raise EmbeddingError("embedding_value_invalid")
        normalized = [float(v) for v in vector]
        if not any(normalized):
            raise EmbeddingError("embedding_zero_vector")
        result.append(normalized)
    return result


class FakeEmbeddingProvider:
    provider, model, version = "fake", "deterministic-hash", "1"

    def __init__(self, dimensions: int = 32):
        if not 1 <= dimensions <= 2000:
            raise ValueError("Invalid dimensions")
        self.dimensions = dimensions

    def embed(self, inputs: list[str]) -> EmbeddingBatch:
        if not inputs or len(inputs) > 64 or any(not item.strip() or len(item) > 20_000 for item in inputs):
            raise EmbeddingError("embedding_input_invalid")
        vectors = []
        for item in inputs:
            vector = [0.0] * self.dimensions
            for word in re.findall(r"[a-zA-Z0-9_]+", item.lower()) or [item]:
                digest = hashlib.sha256(word.encode()).digest()
                vector[int.from_bytes(digest[:4], "big") % self.dimensions] += 1.0
            vectors.append(vector)
        return EmbeddingBatch(validate_vectors(vectors, len(inputs), self.dimensions), 0, 0.0)


class OpenAIEmbeddingProvider:
    provider, version = "openai", "embeddings-v1"

    def __init__(self, model: str, dimensions: int, api_key: str, *, allow_paid: bool = False,
                 cost_per_million: float | None = None, transport: httpx.BaseTransport | None = None,
                 max_attempts: int = 3, sleep=time.sleep):
        if not allow_paid:
            raise EmbeddingError("paid_embeddings_not_authorized")
        if not model or not api_key or not 1 <= dimensions <= 2000:
            raise ValueError("Invalid embedding configuration")
        if cost_per_million is not None and (not math.isfinite(cost_per_million) or cost_per_million < 0):
            raise ValueError("Invalid cost configuration")
        if not 1 <= max_attempts <= 3:
            raise ValueError("Invalid retry configuration")
        self.model, self.dimensions, self._api_key = model, dimensions, api_key
        self.cost_per_million, self.transport = cost_per_million, transport
        self.max_attempts, self.sleep = max_attempts, sleep

    def embed(self, inputs: list[str]) -> EmbeddingBatch:
        if not inputs or len(inputs) > 64 or any(not text.strip() or len(text) > 20_000 for text in inputs):
            raise EmbeddingError("embedding_input_invalid")
        try:
            with httpx.Client(timeout=20, follow_redirects=False, transport=self.transport) as client:
                for attempt in range(self.max_attempts):
                    try:
                        response = client.post("https://api.openai.com/v1/embeddings",
                            headers={"Authorization": "Bearer " + self._api_key},
                            json={"model": self.model, "input": inputs, "dimensions": self.dimensions})
                        if response.status_code != 429 and response.status_code < 500:
                            response.raise_for_status()
                            break
                        response.raise_for_status()
                    except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
                        retryable = not isinstance(exc, httpx.HTTPStatusError) or exc.response.status_code == 429 or exc.response.status_code >= 500
                        if not retryable or attempt + 1 == self.max_attempts:
                            raise
                        self.sleep(min(2 ** attempt * 0.25, 1.0))
                data = response.json()
            rows = data["data"]
            if not isinstance(rows, list) or len(rows) != len(inputs):
                raise ValueError("invalid response")
            ordered = sorted(rows, key=lambda row: row["index"])
            if [row["index"] for row in ordered] != list(range(len(inputs))):
                raise ValueError("invalid indexes")
            tokens = data["usage"]["total_tokens"]
            if not isinstance(tokens, int) or isinstance(tokens, bool) or tokens < 0:
                raise ValueError("invalid usage")
            vectors = validate_vectors([row["embedding"] for row in ordered], len(inputs), self.dimensions)
            cost = None if self.cost_per_million is None else tokens * self.cost_per_million / 1_000_000
            return EmbeddingBatch(vectors, tokens, cost)
        except (httpx.HTTPError, ValueError, TypeError, KeyError, IndexError):
            raise EmbeddingError("embedding_provider_failed") from None


def configured_provider() -> EmbeddingProvider:
    from app.core.config import get_settings

    config = get_settings()
    if config.embedding_provider == "fake":
        return FakeEmbeddingProvider(config.embedding_dimensions)
    if config.embedding_provider == "openai":
        return OpenAIEmbeddingProvider(config.embedding_model, config.embedding_dimensions,
            config.embedding_api_key.get_secret_value(), allow_paid=config.embedding_allow_paid)
    raise EmbeddingError("embedding_provider_disabled")
