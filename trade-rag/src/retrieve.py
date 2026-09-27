# -*- coding: utf-8 -*-
"""用問題向 FAISS 找最相關的 chunk（還沒有 LLM）。

P0：真實 MMR（Maximal Marginal Relevance）在候選池上做多樣性取回，
然後再以 KEYWORD_BOOSTS 做輕量 re-rank（僅在 MMR 已選集合）。

P1：多 store（trade / course / admit）分離 FAISS；各 store 搜索後
按 final score 合併取 global top_k。
"""
from __future__ import annotations

import argparse
import os
import sys

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from embedder import encode_query, get_model
from stores import discover_stores, load_stores

DEFAULT_FETCH_K = 24
DEFAULT_LAMBDA = 0.7

# query substring -> boost if also in chunk text/heading
KEYWORD_BOOSTS = [
    (["severe", "2%", "預算池", "cool", "cooling", "hot"], 0.15),
    (["關稅", "減碼", "縮池", "縮預算"], 0.18),
    (["硬關", "收黑", "red_day", "戰爭", "盤崩"], 0.15),
    (["軟關", "最多", "1 檔", "一檔", "max_new"], 0.15),
    (["夜盤", "不進場", "只看盤"], 0.2),
    (["盤中", "預警", "不成交"], 0.15),
    (["零股", "5 股", "1 股", "買不起"], 0.2),
]


def _keyword_bonus(query: str, chunk: dict, *, store: str | None = None) -> float:
    """Trade-oriented keyword boost; skip for non-trade stores."""
    if store is not None and store != "trade":
        return 0.0
    q = query.lower()
    blob = f"{chunk.get('heading', '')}\n{chunk.get('text', '')}".lower()
    bonus = 0.0
    for keys, w in KEYWORD_BOOSTS:
        if any(k.lower() in q for k in keys) and any(k.lower() in blob for k in keys):
            bonus += w
    # prefer denser rule sections a bit
    if "規則" in chunk.get("heading", ""):
        bonus += 0.05
    return bonus


def _encode_query(model: SentenceTransformer, query: str) -> np.ndarray:
    # 走 embedder 的快取：同一句話只 encode 一次（路由器已經算過就直接拿）
    name = getattr(model, "_trade_rag_name", None)
    if name:
        return encode_query(query, name)
    q = model.encode([query], normalize_embeddings=True)
    return np.asarray(q, dtype="float32")


def _reconstruct_vectors(index: faiss.Index, ids: np.ndarray) -> np.ndarray:
    """Prefer FAISS reconstruct (IndexFlatIP) over re-embedding candidates."""
    vecs = []
    for i in ids:
        vi = int(i)
        if vi < 0:
            continue
        vecs.append(index.reconstruct(vi))
    if not vecs:
        return np.zeros((0, index.d), dtype="float32")
    return np.asarray(vecs, dtype="float32")


def _mmr_select(
    query_vec: np.ndarray,
    doc_vecs: np.ndarray,
    lambda_mult: float,
    top_k: int,
) -> tuple[list[int], list[float]]:
    """Classic MMR over candidate vectors.

    Returns (indices into doc_vecs in selection order, mmr_score at pick time).
    """
    n = int(doc_vecs.shape[0])
    if n == 0:
        return [], []
    top_k = min(top_k, n)
    q = query_vec.reshape(-1)
    q_sims = doc_vecs @ q  # cosine / IP on normalized vectors

    selected: list[int] = []
    mmr_scores: list[float] = []
    remaining = set(range(n))

    for _ in range(top_k):
        best_i = -1
        best_score = -1e18
        for i in remaining:
            if not selected:
                score = float(q_sims[i])
            else:
                max_sim = max(float(np.dot(doc_vecs[i], doc_vecs[j])) for j in selected)
                score = float(lambda_mult) * float(q_sims[i]) - (1.0 - float(lambda_mult)) * max_sim
            if score > best_score:
                best_score = score
                best_i = i
        selected.append(best_i)
        mmr_scores.append(best_score)
        remaining.remove(best_i)

    return selected, mmr_scores


def _attach_store(chunk: dict, store: str) -> dict:
    chunk["store"] = store
    return chunk


def _search_no_mmr(
    query: str,
    index: faiss.Index,
    meta: dict,
    model: SentenceTransformer,
    top_k: int,
    fetch_k: int,
    store: str,
) -> list[dict]:
    """Legacy path: FAISS pool + keyword bonus, then top_k."""
    q = _encode_query(model, query)
    k = min(max(fetch_k, top_k), index.ntotal)
    if k <= 0 or index.ntotal <= 0:
        return []
    scores, ids = index.search(q, k)
    scored: list[dict] = []
    for score, idx in zip(scores[0], ids[0]):
        if idx < 0:
            continue
        chunk = dict(meta["chunks"][int(idx)])
        faiss_score = float(score)
        bonus = _keyword_bonus(query, chunk, store=store)
        chunk["faiss_score"] = faiss_score
        chunk["mmr_score"] = None
        chunk["keyword_bonus"] = bonus
        chunk["mmr_rank"] = None
        chunk["score"] = faiss_score + bonus
        scored.append(_attach_store(chunk, store))
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]


def _search_mmr(
    query: str,
    index: faiss.Index,
    meta: dict,
    model: SentenceTransformer,
    top_k: int,
    fetch_k: int,
    lambda_mult: float,
    store: str,
) -> list[dict]:
    q = _encode_query(model, query)
    k_fetch = min(max(fetch_k, top_k), index.ntotal)
    if k_fetch <= 0 or index.ntotal <= 0:
        return []
    scores, ids = index.search(q, k_fetch)

    cand_ids: list[int] = []
    cand_faiss: list[float] = []
    for score, idx in zip(scores[0], ids[0]):
        if idx < 0:
            continue
        cand_ids.append(int(idx))
        cand_faiss.append(float(score))

    if not cand_ids:
        return []

    doc_vecs = _reconstruct_vectors(index, np.asarray(cand_ids, dtype=np.int64))
    if doc_vecs.shape[0] != len(cand_ids):
        rebuilt_ids: list[int] = []
        rebuilt_faiss: list[float] = []
        vecs = []
        for i, fid in enumerate(cand_ids):
            try:
                vecs.append(index.reconstruct(fid))
                rebuilt_ids.append(fid)
                rebuilt_faiss.append(cand_faiss[i])
            except Exception:
                continue
        cand_ids, cand_faiss = rebuilt_ids, rebuilt_faiss
        doc_vecs = np.asarray(vecs, dtype="float32")

    query_vec = q[0]
    order, mmr_at_pick = _mmr_select(query_vec, doc_vecs, lambda_mult, top_k)

    selected: list[dict] = []
    for mmr_rank, local_i in enumerate(order, 1):
        idx = cand_ids[local_i]
        chunk = dict(meta["chunks"][idx])
        faiss_score = cand_faiss[local_i]
        bonus = _keyword_bonus(query, chunk, store=store)
        chunk["faiss_score"] = faiss_score
        chunk["mmr_score"] = float(mmr_at_pick[mmr_rank - 1])
        chunk["keyword_bonus"] = bonus
        chunk["mmr_rank"] = mmr_rank
        chunk["score"] = faiss_score + bonus
        selected.append(_attach_store(chunk, store))

    selected.sort(key=lambda x: x["score"], reverse=True)
    return selected


def _search_one_store(
    query: str,
    store_name: str,
    index: faiss.Index,
    meta: dict,
    model: SentenceTransformer,
    top_k: int,
    fetch_k: int,
    lambda_mult: float,
    use_mmr: bool,
) -> list[dict]:
    if not use_mmr:
        return _search_no_mmr(query, index, meta, model, top_k, fetch_k, store_name)
    return _search_mmr(query, index, meta, model, top_k, fetch_k, lambda_mult, store_name)


def search(
    query: str,
    top_k: int = 5,
    pool: int | None = None,
    fetch_k: int = DEFAULT_FETCH_K,
    lambda_mult: float = DEFAULT_LAMBDA,
    use_mmr: bool | None = None,
    store: str | None = None,
) -> list[dict]:
    """Retrieve top_k chunks for query across enabled FAISS stores.

    Backward compatible: `search(query, top_k=5)` and optional legacy `pool`
    (maps to fetch_k when provided).

    `store`: if set (e.g. `"trade"`), query only that store; otherwise all
    discovered stores with real indexes. Empty course/admit are skipped.

    Per-store: MMR + keyword boost (keyword boost only for trade). Results are
    merged by final score into a global top_k. Each hit has a `store` field.
    """
    if pool is not None:
        fetch_k = int(pool)

    if use_mmr is None:
        env = os.environ.get("TRADE_RAG_NO_MMR", "").strip().lower()
        use_mmr = env not in ("1", "true", "yes", "on")

    if store:
        handles = load_stores([store])
        if not handles:
            raise FileNotFoundError(
                f"store {store!r} has no index (need index.faiss + index_meta.pkl)"
            )
    else:
        handles = load_stores(None)
        if not handles:
            discovered = discover_stores()
            raise FileNotFoundError(
                f"no FAISS stores under indexes/ (discovered={discovered})"
            )

    # One shared embedder: prefer first store's model_name
    model_name = handles[0].meta.get("model_name") or (
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )
    # 模型只載入一次（原本每次 search 都重新載入，約數秒）
    model = get_model(model_name)
    model._trade_rag_name = model_name

    all_hits: list[dict] = []
    for h in handles:
        hits = _search_one_store(
            query,
            h.name,
            h.index,
            h.meta,
            model,
            top_k=top_k,
            fetch_k=fetch_k,
            lambda_mult=lambda_mult,
            use_mmr=use_mmr,
        )
        all_hits.extend(hits)

    all_hits.sort(key=lambda x: x["score"], reverse=True)
    return all_hits[:top_k]


def _preview(text: str, n: int = 200) -> str:
    return (text or "")[:n].replace("\n", " | ")


def _print_hits(
    query: str,
    hits: list[dict],
    *,
    use_mmr: bool,
    fetch_k: int,
    lambda_mult: float,
    store_filter: str | None,
) -> None:
    mode = "MMR+keyword" if use_mmr else "FAISS+keyword (no-mmr)"
    store_txt = store_filter or "all"
    print(f"Q: {query}")
    print(
        f"mode={mode}  store={store_txt}  "
        f"top_k={len(hits)}  fetch_k={fetch_k}  lambda={lambda_mult}"
    )
    for i, hit in enumerate(hits, 1):
        faiss_s = hit.get("faiss_score")
        mmr_s = hit.get("mmr_score")
        bonus = hit.get("keyword_bonus", 0.0)
        mmr_rank = hit.get("mmr_rank")
        store_name = hit.get("store", "?")
        faiss_txt = f"{faiss_s:.4f}" if faiss_s is not None else "n/a"
        mmr_txt = f"{mmr_s:.4f}" if mmr_s is not None else "n/a"
        rank_txt = str(mmr_rank) if mmr_rank is not None else "-"
        print(
            f"\n#{i} store={store_name}  final={hit['score']:.4f}  "
            f"faiss={faiss_txt}  mmr={mmr_txt}  kw_bonus={bonus:.3f}  mmr_rank={rank_txt}"
        )
        print(f"  {hit.get('source', '?')} / {hit.get('heading', '?')}")
        print(f"  {_preview(hit.get('text', ''))}")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="trade-rag retrieve (multi-store MMR + keyword boost)")
    p.add_argument(
        "query",
        nargs="*",
        help="query text (Traditional Chinese ok)",
    )
    p.add_argument(
        "--retrieve-only",
        action="store_true",
        help="print ranked chunks with scores (no LLM; default behavior of this script)",
    )
    p.add_argument(
        "--store",
        default=None,
        help="query only this store (trade|course|admit); default: all with indexes",
    )
    p.add_argument("--top-k", type=int, default=5, help="number of results (default 5)")
    p.add_argument(
        "--fetch-k",
        type=int,
        default=DEFAULT_FETCH_K,
        help=f"FAISS candidate pool size before MMR (default {DEFAULT_FETCH_K})",
    )
    p.add_argument(
        "--lambda",
        dest="lambda_mult",
        type=float,
        default=DEFAULT_LAMBDA,
        help=f"MMR lambda (relevance vs diversity, default {DEFAULT_LAMBDA})",
    )
    p.add_argument(
        "--no-mmr",
        action="store_true",
        help="disable MMR; use legacy FAISS pool + keyword boost only",
    )
    return p.parse_args(argv)


if __name__ == "__main__":
    # Windows console may mojibake CJK; keep stdout UTF-8 when possible
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    args = _parse_args()
    query = " ".join(args.query).strip() or "severe 預算池是多少"
    use_mmr = not args.no_mmr
    hits = search(
        query,
        top_k=args.top_k,
        fetch_k=args.fetch_k,
        lambda_mult=args.lambda_mult,
        use_mmr=use_mmr,
        store=args.store,
    )
    _print_hits(
        query,
        hits,
        use_mmr=use_mmr,
        fetch_k=args.fetch_k,
        lambda_mult=args.lambda_mult,
        store_filter=args.store,
    )
