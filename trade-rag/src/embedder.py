# -*- coding: utf-8 -*-
"""共用的 embedding 模型（整個程序只載入一次）。

原本 retrieve.search() 每問一次就重新 SentenceTransformer(...)，要好幾秒；
改成這裡快取後，路由器（要對每個 store 打分）與 RAG 檢索共用同一個模型，
而且同一句問題只 encode 一次（lru_cache）。
"""
from __future__ import annotations

import threading
from functools import lru_cache

import numpy as np

from config import EMBED_MODEL_NAME

_models: dict = {}
_lock = threading.Lock()


def get_model(name: str | None = None):
    name = name or EMBED_MODEL_NAME
    with _lock:
        m = _models.get(name)
        if m is None:
            from sentence_transformers import SentenceTransformer

            m = SentenceTransformer(name)
            _models[name] = m
        return m


@lru_cache(maxsize=512)
def _encode_cached(name: str, text: str) -> bytes:
    m = get_model(name)
    with _lock:
        v = m.encode([text], normalize_embeddings=True)
    return np.asarray(v, dtype="float32").tobytes()


def encode_query(text: str, name: str | None = None) -> np.ndarray:
    """回傳 shape=(1, dim) 的正規化向量（cosine = 內積）。"""
    name = name or EMBED_MODEL_NAME
    buf = _encode_cached(name, text or "")
    v = np.frombuffer(buf, dtype="float32")
    return v.reshape(1, -1).copy()


def encode_texts(texts: list[str], name: str | None = None, show_progress: bool = False) -> np.ndarray:
    m = get_model(name)
    with _lock:
        v = m.encode(texts, normalize_embeddings=True, show_progress_bar=show_progress)
    return np.asarray(v, dtype="float32")
