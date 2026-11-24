"""Opt-in local ONNX inference; reads only explicitly pinned local artifacts.

No download, model-supplied Python, custom operators or network client is used.
Inference dependencies are imported only when actual inference is requested.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sys
import threading
from importlib.util import find_spec
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import Callable

from app.modules.ingestion.embeddings import EmbeddingBatch, EmbeddingError, validate_vectors


@dataclass(frozen=True)
class ModelSpec:
    dimensions: int
    tokens: int
    pooling: str
    query_prefix: str
    input_names: tuple[str, ...] = ()
    output_name: str | None = None
    special_tokens: tuple[tuple[str, int], ...] = ()


MODELS = {
    "nomic-ai/CodeRankEmbed": ModelSpec(768, 512, "cls", "Represent this query for searching relevant code: ",
        ("input_ids", "attention_mask", "token_type_ids"), "last_hidden_state",
        (("[PAD]", 0), ("[CLS]", 101), ("[SEP]", 102))),
    "sentence-transformers/all-MiniLM-L6-v2": ModelSpec(384, 256, "mean", ""),
}
_INFERENCE_SLOT = threading.BoundedSemaphore(1)


def _check_runtime_versions() -> None:
    try:
        if metadata.version("onnxruntime") != "1.31.1" or metadata.version("tokenizers") != "0.23.3":
            raise EmbeddingError("LOCAL_RUNTIME_INCOMPATIBLE")
        metadata.version("numpy")
    except metadata.PackageNotFoundError:
        raise EmbeddingError("LOCAL_RUNTIME_NOT_AVAILABLE") from None


def _artifact(root: Path, name: str, expected: str, limit: int, *, read: bool = True) -> bytes:
    path = root / name
    try:
        if not root.is_absolute() or root.is_symlink() or path.is_symlink() or not path.is_file():
            raise EmbeddingError("MODEL_NOT_AVAILABLE")
        if path.stat().st_size > limit:
            raise EmbeddingError("MODEL_NOT_AVAILABLE")
        digest = hashlib.sha256()
        parts = []
        total = 0
        with path.open("rb") as stream:
            while block := stream.read(1024 * 1024):
                total += len(block)
                if total > limit:
                    raise EmbeddingError("MODEL_NOT_AVAILABLE")
                digest.update(block)
                if read:
                    parts.append(block)
    except OSError:
        raise EmbeddingError("MODEL_NOT_AVAILABLE") from None
    if not total or digest.hexdigest() != expected:
        raise EmbeddingError("MODEL_NOT_AVAILABLE")
    return b"".join(parts)


def _validate_signature(session, spec: ModelSpec) -> None:
    """Reject a CodeRank export that does not match its documented graph contract."""
    if not spec.input_names:
        return
    inputs, outputs = session.get_inputs(), session.get_outputs()
    if (len(inputs) != len(spec.input_names) or {item.name for item in inputs} != set(spec.input_names)
            or any(item.type != "tensor(int64)" or len(item.shape) != 2 for item in inputs)
            or len(outputs) != 1 or outputs[0].name != spec.output_name
            or outputs[0].type != "tensor(float)" or len(outputs[0].shape) != 3
            or (isinstance(outputs[0].shape[2], int) and outputs[0].shape[2] != spec.dimensions)):
        raise ValueError("incompatible_model_signature")


def _validate_tokenizer(tokenizer, encoded, spec: ModelSpec) -> None:
    if not spec.special_tokens:
        return
    if any(tokenizer.token_to_id(token) != expected for token, expected in spec.special_tokens):
        raise ValueError("incompatible_tokenizer")
    for item in encoded:
        active = sum(item.attention_mask)
        if (active < 2 or item.ids[0] != 101 or item.ids[active - 1] != 102
                or item.attention_mask != [1] * active + [0] * (len(item.ids) - active)):
            raise ValueError("incompatible_tokenizer")


def _pool_hidden(output, attention_mask, spec: ModelSpec):
    if (output.ndim != 3 or output.shape[0] != attention_mask.shape[0]
            or output.shape[1] != attention_mask.shape[1] or output.shape[2] != spec.dimensions):
        raise ValueError("invalid_output")
    mask = attention_mask[:, :, None]
    return output[:, 0, :] if spec.pooling == "cls" else (output * mask).sum(axis=1) / mask.sum(axis=1)


def _onnx_runtime(model: bytes, tokenizer: bytes, texts: list[str], spec: ModelSpec) -> list[list[float]]:
    """Use only CPU, bounded threads and standard locally installed runtimes."""
    try:
        _check_runtime_versions()
        if "onnxruntime" in sys.modules and os.environ.get("ORT_DISABLE_TELEMETRY") != "1":
            raise EmbeddingError("LOCAL_RUNTIME_UNSAFE")
        # ONNX Runtime can initialize telemetry at import time. The process-wide
        # opt-out must be in place before the native runtime is first loaded.
        os.environ["ORT_DISABLE_TELEMETRY"] = "1"
        os.environ["TOKENIZERS_PARALLELISM"] = "false"
        import numpy as np
        import onnxruntime as ort
        from tokenizers import Tokenizer
        ort.disable_telemetry_events()
        ort.set_default_logger_severity(4)
    except ImportError:
        raise EmbeddingError("LOCAL_RUNTIME_NOT_AVAILABLE") from None
    try:
        tokenizer_obj = Tokenizer.from_str(tokenizer.decode("utf-8"))
        tokenizer_obj.enable_truncation(max_length=spec.tokens, direction="right")
        tokenizer_obj.enable_padding(direction="right", pad_id=0, pad_type_id=0, pad_token="[PAD]")
        encoded = tokenizer_obj.encode_batch(texts)
        _validate_tokenizer(tokenizer_obj, encoded, spec)
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        options.inter_op_num_threads = 1
        options.log_severity_level = 4
        session = ort.InferenceSession(model, sess_options=options, providers=["CPUExecutionProvider"])
        _validate_signature(session, spec)
        available = {"input_ids": np.array([item.ids for item in encoded], dtype=np.int64),
                     "attention_mask": np.array([item.attention_mask for item in encoded], dtype=np.int64),
                     "token_type_ids": np.array([item.type_ids for item in encoded], dtype=np.int64)}
        names = [entry.name for entry in session.get_inputs()]
        if not names or any(name not in available for name in names):
            raise ValueError("unsupported inputs")
        options_run = ort.RunOptions()
        timer = threading.Timer(10.0, lambda: setattr(options_run, "terminate", True))
        timer.daemon = True
        timer.start()
        try:
            output = session.run([spec.output_name] if spec.output_name else None,
                                 {name: available[name] for name in names}, options_run)[0]
        finally:
            timer.cancel()
        pooled = _pool_hidden(output, available["attention_mask"], spec)
        return pooled.tolist()
    except Exception:
        # Do not log model input, artifact paths, runtime diagnostics or source.
        raise EmbeddingError("LOCAL_INFERENCE_FAILED") from None


class LocalEmbeddingProvider:
    provider = "local-onnx"
    normalization = "l2"

    def __init__(self, *, model: str, revision: str, dimensions: int, root: str,
                 model_sha256: str, tokenizer_sha256: str, tokenizer_revision: str | None = None, enabled: bool = False,
                 runtime: Callable = _onnx_runtime):
        if not enabled:
            raise EmbeddingError("LOCAL_EMBEDDINGS_DISABLED")
        spec = MODELS.get(model)
        tokenizer_revision = revision if tokenizer_revision is None else tokenizer_revision
        if (not spec or dimensions != spec.dimensions or not re.fullmatch(r"[0-9a-f]{40}", revision)
                or not re.fullmatch(r"[0-9a-f]{40}", tokenizer_revision)
                or not re.fullmatch(r"[0-9a-f]{64}", model_sha256)
                or not re.fullmatch(r"[0-9a-f]{64}", tokenizer_sha256)):
            raise EmbeddingError("LOCAL_CONFIGURATION_INVALID")
        self.model, self.revision, self.dimensions, self.spec = model, revision, dimensions, spec
        self.tokenizer_revision = tokenizer_revision
        self.root, self.model_sha256, self.tokenizer_sha256 = Path(root), model_sha256, tokenizer_sha256
        self.runtime = runtime
        contract = {"version": "local-onnx-v2", "pooling": spec.pooling, "query_prefix": spec.query_prefix,
                    "document_prefix": "", "max_tokens": spec.tokens, "truncation": "right",
                    "normalization": self.normalization, "model_sha256": model_sha256,
                    "tokenizer_sha256": tokenizer_sha256, "tokenizer_revision": tokenizer_revision,
                    "query_prefix_policy": "exactly-once", "padding": "longest-pad0",
                    "input_names": spec.input_names, "output_name": spec.output_name,
                    "special_tokens": spec.special_tokens,
                    "onnxruntime": "1.31.1", "tokenizers": "0.23.3"}
        self.contract = hashlib.sha256(json.dumps(contract, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        # The existing cache uniqueness key includes version; bind the full contract
        # to it while storing the full digest and exact revision separately.
        self.version = revision + ":" + self.contract[:24]

    def available(self) -> None:
        _artifact(self.root, "model.onnx", self.model_sha256, 800_000_000, read=False)
        _artifact(self.root, "tokenizer.json", self.tokenizer_sha256, 20_000_000, read=False)
        if self.runtime is _onnx_runtime and any(find_spec(name) is None for name in ("numpy", "onnxruntime", "tokenizers")):
            raise EmbeddingError("LOCAL_RUNTIME_NOT_AVAILABLE")
        if self.runtime is _onnx_runtime:
            _check_runtime_versions()
        if self.runtime is _onnx_runtime and "onnxruntime" in sys.modules and os.environ.get("ORT_DISABLE_TELEMETRY") != "1":
            raise EmbeddingError("LOCAL_RUNTIME_UNSAFE")

    def _embed(self, inputs: list[str], *, query: bool) -> EmbeddingBatch:
        if not inputs or len(inputs) > 8 or any(not isinstance(item, str) or not item.strip() or len(item) > 20_000 for item in inputs):
            raise EmbeddingError("embedding_input_invalid")
        if not _INFERENCE_SLOT.acquire(blocking=False):
            raise EmbeddingError("LOCAL_MODEL_BUSY")
        try:
            model = _artifact(self.root, "model.onnx", self.model_sha256, 800_000_000)
            tokenizer = _artifact(self.root, "tokenizer.json", self.tokenizer_sha256, 20_000_000)
            texts = []
            for item in inputs:
                if query and self.spec.query_prefix:
                    prefix, suffix = self.spec.query_prefix, item
                    if suffix.lstrip().startswith(prefix):
                        suffix = suffix.lstrip()
                        while suffix.startswith(prefix):
                            suffix = suffix[len(prefix):].lstrip()
                    if not suffix.strip():
                        raise EmbeddingError("embedding_input_invalid")
                    item = prefix + suffix
                texts.append(item)
            vectors = validate_vectors(self.runtime(model, tokenizer, texts, self.spec), len(texts), self.dimensions)
            vectors = [[value / math.hypot(*vector) for value in vector] for vector in vectors]
            return EmbeddingBatch(validate_vectors(vectors, len(texts), self.dimensions), 0, 0.0)
        except EmbeddingError:
            raise
        except Exception:
            raise EmbeddingError("LOCAL_INFERENCE_FAILED") from None
        finally:
            _INFERENCE_SLOT.release()

    def embed(self, inputs: list[str]) -> EmbeddingBatch:
        return self._embed(inputs, query=False)

    def embed_query(self, query: str) -> EmbeddingBatch:
        return self._embed([query], query=True)
