# -*- coding: utf-8 -*-
"""文字後處理：簡轉繁（OpenCC）＋日期守門。

小模型（qwen2.5:3b）偶爾會冒出簡體字；只要偵測到常見簡體字，就用 OpenCC s2twp 轉成台灣繁體。
沒裝 opencc 套件時什麼都不做（不會壞掉）。
"""
from __future__ import annotations

import re

# 常見「只在簡體出現」的字（出現就代表模型飄到簡體）
_SIMP = set("们这个说时会为国么还没发经过学开关对样问题让实现应该给从动书长东车门见觉认识读写语话请谢边钱"
            "还处认记设计总数据库间题资讯频网络软硬件机构层级类变录选择历史场质量虽然尽务专业")
_cc = None


def _converter():
    global _cc
    if _cc is None:
        try:
            from opencc import OpenCC  # pip install opencc-python-reimplemented（純 Python，免費）

            _cc = OpenCC("s2twp")
        except Exception:
            _cc = False
    return _cc


def has_simplified(text: str) -> bool:
    return any(ch in _SIMP for ch in text or "")


def to_traditional(text: str) -> str:
    if not text or not has_simplified(text):
        return text
    cc = _converter()
    if not cc:
        return text
    try:
        return cc.convert(text)
    except Exception:
        return text


DATE_PATTERNS = [
    re.compile(r"(20\d\d)[/-](\d{1,2})[/-](\d{1,2})"),
    re.compile(r"(?<![\d/])(\d{1,2})/(\d{1,2})(?![\d/])"),
    re.compile(r"(\d{1,2})\s*月\s*(\d{1,2})\s*日"),
]


def dates_in(text: str) -> set[tuple[int, int]]:
    """抓出文字中的 (月, 日)，給「答案裡的日期必須出現在資料裡」檢查用。"""
    out = set()
    for m in DATE_PATTERNS[0].finditer(text or ""):
        out.add((int(m.group(2)), int(m.group(3))))
    t2 = DATE_PATTERNS[0].sub(" ", text or "")
    for pat in DATE_PATTERNS[1:]:
        for m in pat.finditer(t2):
            mo, d = int(m.group(1)), int(m.group(2))
            if 1 <= mo <= 12 and 1 <= d <= 31:
                out.add((mo, d))
    return out
