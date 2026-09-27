"""只讀行情／法人狀態：優先面板 API，其次 paper 檔案。不成交、不改 trade。"""
from __future__ import annotations

import csv
import json
import urllib.request
from pathlib import Path

PAPER = Path(r"C:\Users\AUSER\Desktop\trade\snr_backtest\paper")
TWII_CSV = Path(r"C:\Users\AUSER\Desktop\trade\snr_backtest\data\TWII.csv")
PANEL_STATE = "http://127.0.0.1:8501/api/state"
PANEL_INST = "http://127.0.0.1:8501/api/institutional"
DISCLAIMER = "僅狀態描述，非買賣建議。"


def _get_json(url: str, timeout: float = 3.0) -> dict | None:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def _load(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def panel_state() -> dict | None:
    return _get_json(PANEL_STATE)


def institutional_data() -> dict | None:
    data = _get_json(PANEL_INST)
    if data and data.get("ok"):
        return data
    return _load(PAPER / "institutional.json")


def twii_from_csv() -> dict | None:
    if not TWII_CSV.exists():
        return None
    rows = list(csv.DictReader(TWII_CSV.open(encoding="utf-8-sig")))
    if not rows:
        return None
    last = rows[-1]
    prev = rows[-2] if len(rows) >= 2 else None
    close = float(last["Close"])
    prev_c = float(prev["Close"]) if prev else close
    chg = close - prev_c
    return {
        "asof": last["Date"],
        "open": float(last["Open"]),
        "high": float(last["High"]),
        "low": float(last["Low"]),
        "close": close,
        "last": close,
        "chg": chg,
        "chg_pct": (chg / prev_c * 100.0) if prev_c else 0.0,
        "status": "日線快取",
        "source": "TWII.csv",
    }


def format_twii() -> str:
    state = panel_state() or {}
    tw = state.get("twii") if isinstance(state.get("twii"), dict) else None
    if not tw:
        tw = twii_from_csv()
    if not tw:
        return "加權資料未找到（面板未開且無 TWII.csv）。\n" + DISCLAIMER
    last = tw.get("last") or tw.get("close")
    chg = tw.get("chg")
    chg_pct = tw.get("chg_pct")
    asof = tw.get("asof")
    status = tw.get("status") or ""
    sma = ""
    if "above" in tw and tw.get("sma_n"):
        sma = f"；相對 SMA{tw['sma_n']}：" + ("上方" if tw.get("above") else "下方")
    lines = [
        f"加權（{asof} {status}）：收/最新約 {last:,.2f}",
    ]
    if chg is not None and chg_pct is not None:
        sign = "+" if chg >= 0 else ""
        lines[0] += f"（{sign}{chg:,.2f}／{sign}{chg_pct:.2f}%）{sma}"
    lines.append(f"當日 OHLC：{tw.get('open')}／{tw.get('high')}／{tw.get('low')}／{tw.get('close')}")
    lines.append(DISCLAIMER)
    return "\n".join(lines)


def format_txf_night() -> str:
    state = panel_state() or {}
    tx = state.get("txf_night") if isinstance(state.get("txf_night"), dict) else None
    if not tx or not tx.get("ok"):
        return (
            "台指期夜盤即時資料目前讀不到（請確認面板 http://127.0.0.1:8501 有開）。\n"
            "規則面：夜盤只看盤、不進場。\n" + DISCLAIMER
        )
    chg = tx.get("chg")
    chg_pct = tx.get("chg_pct")
    sign = "+" if (chg or 0) >= 0 else ""
    lines = [
        f"台指期夜盤 {tx.get('code')} {tx.get('name')}（{tx.get('month')}）狀態：{tx.get('status')}",
        f"最新 {tx.get('last')}（{sign}{chg}／{sign}{(chg_pct or 0):.2f}%），參考價 {tx.get('ref')}，asof {tx.get('asof')}",
        f"當夜 OHLC：{tx.get('open')}／{tx.get('high')}／{tx.get('low')}／{tx.get('close')}",
        "規則：夜盤只看盤、不進場。",
        DISCLAIMER,
    ]
    return "\n".join(lines)


def format_institutional() -> str:
    data = institutional_data()
    if not data or not data.get("ok"):
        return "三大法人資料尚未抓取或讀取失敗（預期 paper/institutional.json）。\n" + DISCLAIMER
    def _net(block: dict | None) -> str:
        if not block:
            return "—"
        yi = block.get("net_yi")
        if yi is None:
            return "—"
        sign = "+" if yi >= 0 else ""
        return f"{sign}{yi:.2f} 億"

    lines = [
        f"三大法人（{data.get('date')}，來源 {data.get('source')} {data.get('endpoint')}，更新 {data.get('updated_at')}）",
        f"外資淨買賣超 {_net(data.get('foreign'))}；投信 {_net(data.get('trust'))}；自營(自行+避險) {_net(data.get('dealer'))}；合計 {_net(data.get('total'))}",
        DISCLAIMER,
    ]
    return "\n".join(lines)


def format_market_bundle() -> str:
    return "\n\n".join([format_twii(), format_txf_night(), format_institutional()])
