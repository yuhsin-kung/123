# -*- coding: utf-8 -*-
"""Multi-store FAISS discovery and load (raw faiss, no LangChain).

Layout:
  indexes/<store>/index.faiss
  indexes/<store>/index_meta.pkl
  indexes/<store>/chunks.jsonl   (optional; used by build/ingest for trade)

Empty placeholders (course/, admit/ without index files) are skipped.
Flat legacy indexes/index.faiss is migrated into indexes/trade/ on first load.
"""
from __future__ import annotations

import pickle
import shutil
from dataclasses import dataclass
from pathlib import Path

import faiss

from config import (
    ANCHOR_FAISS_NAME,
    ANCHOR_META_NAME,
    DEFAULT_STORE,
    FAISS_NAME,
    INDEX_DIR,
    META_NAME,
    PENDING_INDEX_DIR,
    STORE_CONFIG_NAME,
    STORE_NAMES,
)


@dataclass
class StoreHandle:
    name: str
    path: Path
    index: faiss.Index
    meta: dict


def store_dir(name: str) -> Path:
    """indexes/<name>；若那裡沒有索引但 indexes/_pending/<name> 有，就用待上線的那份。"""
    p = INDEX_DIR / name
    if not store_has_index(p) and store_has_index(PENDING_INDEX_DIR / name):
        return PENDING_INDEX_DIR / name
    return p


def build_dir(name: str) -> Path:
    """建索引要寫到哪：已上線（indexes/<name> 有索引）就原地重建，否則寫進 _pending。"""
    p = INDEX_DIR / name
    if store_has_index(p):
        return p
    return PENDING_INDEX_DIR / name


def store_has_index(path: Path) -> bool:
    return (path / FAISS_NAME).is_file() and (path / META_NAME).is_file()


def migrate_flat_index_if_needed() -> bool:
    """Move flat indexes/index.faiss (+ meta, chunks) into indexes/trade/.

    Returns True if a migration happened.
    """
    flat_faiss = INDEX_DIR / FAISS_NAME
    flat_meta = INDEX_DIR / META_NAME
    flat_chunks = INDEX_DIR / "chunks.jsonl"
    dest = store_dir(DEFAULT_STORE)
    dest.mkdir(parents=True, exist_ok=True)

    moved = False
    if flat_faiss.is_file() and not (dest / FAISS_NAME).exists():
        shutil.move(str(flat_faiss), str(dest / FAISS_NAME))
        moved = True
    elif flat_faiss.is_file() and (dest / FAISS_NAME).exists():
        flat_faiss.unlink()
        moved = True

    if flat_meta.is_file() and not (dest / META_NAME).exists():
        shutil.move(str(flat_meta), str(dest / META_NAME))
        moved = True
    elif flat_meta.is_file() and (dest / META_NAME).exists():
        flat_meta.unlink()
        moved = True

    if flat_chunks.is_file() and not (dest / "chunks.jsonl").exists():
        shutil.move(str(flat_chunks), str(dest / "chunks.jsonl"))
        moved = True
    elif flat_chunks.is_file() and (dest / "chunks.jsonl").exists():
        flat_chunks.unlink()
        moved = True

    return moved


def ensure_placeholder_dirs() -> None:
    """Create empty domain dirs so layout is visible."""
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    for name in STORE_NAMES:
        d = store_dir(name)
        d.mkdir(parents=True, exist_ok=True)


def discover_stores(index_dir: Path | None = None) -> list[str]:
    """Return store names under INDEX_DIR that have both index files.

    Prefer known STORE_NAMES order; also pick up any other subdir with indexes.
    Empty placeholders (no faiss/meta) are omitted — never crash.
    """
    migrate_flat_index_if_needed()
    ensure_placeholder_dirs()
    root = index_dir or INDEX_DIR
    if not root.is_dir():
        return []

    found: list[str] = []
    seen: set[str] = set()

    # Prefer canonical order
    for name in STORE_NAMES:
        p = root / name
        if store_has_index(p):
            found.append(name)
            seen.add(name)

    # Any extra subdirs with real indexes
    for p in sorted(root.iterdir()):
        if not p.is_dir() or p.name in seen:
            continue
        if store_has_index(p):
            found.append(p.name)
            seen.add(p.name)

    return found


def load_store(name: str) -> StoreHandle:
    path = store_dir(name)
    if not store_has_index(path):
        raise FileNotFoundError(f"store {name!r} missing index at {path}")
    index = faiss.read_index(str(path / FAISS_NAME))
    with (path / META_NAME).open("rb") as f:
        meta = pickle.load(f)
    return StoreHandle(name=name, path=path, index=index, meta=meta)


def load_stores(names: list[str] | None = None) -> list[StoreHandle]:
    """Load enabled stores. names=None means all discovered."""
    migrate_flat_index_if_needed()
    if names is None:
        names = discover_stores()
    else:
        # filter to those that actually have indexes
        names = [n for n in names if store_has_index(store_dir(n))]
    return [load_store(n) for n in names]


# ---------------------------------------------------------------------------
# 路由器用：快取的 store（內容索引＋錨點問句索引），檔案有更新就自動重讀
# ---------------------------------------------------------------------------
_cache: dict[str, tuple[float, "StoreHandle | None", tuple | None]] = {}


def _mtime(path: Path) -> float:
    t = 0.0
    for n in (FAISS_NAME, META_NAME, ANCHOR_FAISS_NAME, ANCHOR_META_NAME):
        f = path / n
        if f.is_file():
            t = max(t, f.stat().st_mtime)
    return t


def load_anchors(name: str):
    """indexes/<store>/anchors.faiss + anchors_meta.pkl（可選）。沒有就回 None。"""
    path = store_dir(name)
    fa, fm = path / ANCHOR_FAISS_NAME, path / ANCHOR_META_NAME
    if not (fa.is_file() and fm.is_file()):
        # 錨點也可能放在 _pending/<name>/（例如 trade 已上線、錨點還在待上線）
        fa, fm = PENDING_INDEX_DIR / name / ANCHOR_FAISS_NAME, PENDING_INDEX_DIR / name / ANCHOR_META_NAME
        if not (fa.is_file() and fm.is_file()):
            return None
    index = faiss.read_index(str(fa))
    with fm.open("rb") as f:
        meta = pickle.load(f)
    return index, meta


def discover_all_stores() -> dict[str, Path]:
    """v2 用：走訪 indexes/ 與 indexes/_pending/ 的每個資料夾，有索引檔的就是一個 store。

    新增知識庫＝新增一個資料夾（index.faiss + index_meta.pkl，可再加 store.json），不必改程式。
    同名時以 indexes/ 正式版優先。
    """
    out: dict[str, Path] = {}
    for root in (INDEX_DIR, PENDING_INDEX_DIR):
        if not root.is_dir():
            continue
        for p in sorted(root.iterdir()):
            if p.is_dir() and not p.name.startswith("_") and p.name not in out and store_has_index(p):
                out[p.name] = p
    return out


def store_config(name: str) -> dict:
    import json

    f = store_dir(name) / STORE_CONFIG_NAME
    if f.is_file():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def cached_store(name: str):
    """回傳 (StoreHandle 或 None, anchors 或 None)，依檔案 mtime 快取。"""
    path = store_dir(name)
    mt = max(_mtime(path), _mtime(PENDING_INDEX_DIR / name))
    hit = _cache.get(name)
    if hit and hit[0] == mt:
        return hit[1], hit[2]
    handle = load_store(name) if store_has_index(path) else None
    anchors = load_anchors(name)
    _cache[name] = (mt, handle, anchors)
    return handle, anchors
