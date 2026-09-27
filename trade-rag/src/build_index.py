# -*- coding: utf-8 -*-
"""將 chunks.jsonl 建成 FAISS 向量庫（寫入 indexes/trade/）。

流程（用小龍常用語說明）：
1. 讀每筆 chunk 的 text
2. 用 embedding 模型把文字變成向量（一串數字，意思相近的會靠近）
3. 存進 FAISS，以後用「問題向量」找最靠近的幾筆

模型用多語小型模型，在本機 CPU 也行；以後要換 BGE-M3 改 MODEL_NAME。
"""
from __future__ import annotations

import json
import pickle

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from config import CHUNKS_PATH, FAISS_NAME, META_NAME, TRADE_INDEX_DIR

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
FAISS_PATH = TRADE_INDEX_DIR / FAISS_NAME
META_PATH = TRADE_INDEX_DIR / META_NAME


def load_chunks() -> list[dict]:
    rows = []
    with CHUNKS_PATH.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    if not rows:
        raise SystemExit(f"no chunks in {CHUNKS_PATH}; run ingest.py first")
    return rows


def build_index() -> None:
    chunks = load_chunks()
    texts = [c["text"] for c in chunks]
    print(f"loading model: {MODEL_NAME}")
    model = SentenceTransformer(MODEL_NAME)
    print(f"embedding {len(texts)} chunks…")
    vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=True)
    vectors = np.asarray(vectors, dtype="float32")

    index = faiss.IndexFlatIP(vectors.shape[1])  # cosine via normalized IP
    index.add(vectors)

    TRADE_INDEX_DIR.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(FAISS_PATH))
    with META_PATH.open("wb") as f:
        pickle.dump({"model_name": MODEL_NAME, "chunks": chunks}, f)

    print(f"wrote {FAISS_PATH} ({index.ntotal} vectors, dim={vectors.shape[1]})")
    print(f"wrote {META_PATH}")


if __name__ == "__main__":
    build_index()
