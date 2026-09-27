"""把規則 Markdown 切成可檢索的小段（chunks）。

切法：先依 ##，再依 ###。硬關／軟關分開放，小模型比較不容易混。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from config import CHUNKS_PATH, RULES_DIR, TRADE_INDEX_DIR


H2_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
H3_RE = re.compile(r"^###\s+(.+?)\s*$", re.MULTILINE)


def _split_by_header(text: str, pattern: re.Pattern[str]) -> list[tuple[str, str]]:
    parts = pattern.split(text)
    out: list[tuple[str, str]] = []
    preamble = parts[0].strip()
    it = iter(parts[1:])
    for heading, body in zip(it, it):
        body = body.strip()
        if body:
            out.append((heading.strip(), body))
    if preamble and not out:
        out.append(("全文", preamble))
    return out


def split_markdown(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []

    title = path.stem
    first = text.splitlines()[0].lstrip("# ").strip()
    if first:
        title = first

    chunks: list[dict] = []
    for h2, body2 in _split_by_header(text, H2_RE):
        # drop the leading # title block if H2 split left only title in preamble — already handled
        sub = _split_by_header(body2, H3_RE)
        if len(sub) >= 2 or (sub and sub[0][0] != "全文" and "###" in body2):
            for h3, body3 in sub:
                if h3 == "全文":
                    heading = h2
                    body = body3
                else:
                    heading = f"{h2} / {h3}"
                    body = body3
                chunks.append(
                    {
                        "source": path.name,
                        "heading": heading,
                        "title": title,
                        "text": body,
                    }
                )
        else:
            chunks.append(
                {
                    "source": path.name,
                    "heading": h2,
                    "title": title,
                    "text": body2,
                }
            )
    return chunks


def build_chunks() -> list[dict]:
    TRADE_INDEX_DIR.mkdir(parents=True, exist_ok=True)
    all_chunks: list[dict] = []
    for path in sorted(RULES_DIR.glob("*.md")):
        # skip pure title-only
        all_chunks.extend(split_markdown(path))

    # remove accidental chunks that are only the H1 line residue
    cleaned = []
    for c in all_chunks:
        if c["heading"] in {"1. 目的", "2. 適用範圍", "3. 規則", "4. 注意"} or " / " in c["heading"]:
            cleaned.append(c)
        elif c["text"].strip():
            cleaned.append(c)

    with CHUNKS_PATH.open("w", encoding="utf-8") as f:
        for i, c in enumerate(cleaned):
            f.write(json.dumps({"id": i, **c}, ensure_ascii=False) + "\n")
    return cleaned


if __name__ == "__main__":
    chunks = build_chunks()
    print(f"wrote {len(chunks)} chunks -> {CHUNKS_PATH}")
    for c in chunks:
        print("-", c["source"], "/", c["heading"], f"({len(c['text'])} chars)")
