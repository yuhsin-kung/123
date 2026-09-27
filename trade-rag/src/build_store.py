# -*- coding: utf-8 -*-
"""通用的「建一個 store」工具：chunks → embedding → FAISS（indexes/<store>/）。

build_index.py 是 trade 專用（保持原樣）；新的 store（scu、general）都走這裡，
輸出格式與 trade 完全相同，所以 retrieve.search(store=...) 與路由器都能直接讀。
"""
from __future__ import annotations

import json
import pickle

import faiss
import numpy as np

from config import ANCHOR_FAISS_NAME, ANCHOR_META_NAME, EMBED_MODEL_NAME, FAISS_NAME, META_NAME, STORE_CONFIG_NAME
from embedder import encode_texts
from stores import PENDING_INDEX_DIR, build_dir


def write_store(name: str, chunks: list[dict], embed_field: str = "text", config: dict | None = None) -> None:
    """chunks: [{source, heading, title, text, ...}]；embed_field 決定拿哪個欄位做向量。
    寫到 build_dir(name)：已上線就原地重建，新 store 先進 indexes/_pending/。"""
    d = build_dir(name)
    d.mkdir(parents=True, exist_ok=True)
    rows = [{"id": i, **c} for i, c in enumerate(chunks)]
    with (d / "chunks.jsonl").open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    texts = [str(r.get(embed_field) or r.get("text") or "") for r in rows]
    vecs = encode_texts(texts, show_progress=False)
    index = faiss.IndexFlatIP(vecs.shape[1])  # cosine via normalized IP
    index.add(np.asarray(vecs, dtype="float32"))
    faiss.write_index(index, str(d / FAISS_NAME))
    with (d / META_NAME).open("wb") as f:
        pickle.dump({"model_name": EMBED_MODEL_NAME, "chunks": rows}, f)
    if config:
        (d / STORE_CONFIG_NAME).write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[{name}] wrote {index.ntotal} vectors (dim={vecs.shape[1]}) -> {d}")


def write_anchors(name: str, texts: list[str]) -> None:
    """路由用錨點問句：indexes/<store>/anchors.faiss（不影響該 store 的內容檢索）。"""
    # 錨點一律放 _pending/<name>/：不碰已上線資料夾（舊版 7860 完全看不到）
    d = PENDING_INDEX_DIR / name
    d.mkdir(parents=True, exist_ok=True)
    texts = [t.strip() for t in texts if t.strip()]
    vecs = encode_texts(texts)
    index = faiss.IndexFlatIP(vecs.shape[1])
    index.add(np.asarray(vecs, dtype="float32"))
    faiss.write_index(index, str(d / ANCHOR_FAISS_NAME))
    with (d / ANCHOR_META_NAME).open("wb") as f:
        pickle.dump({"model_name": EMBED_MODEL_NAME, "texts": texts}, f)
    print(f"[{name}] wrote {index.ntotal} anchor vectors -> {d / ANCHOR_FAISS_NAME}")
