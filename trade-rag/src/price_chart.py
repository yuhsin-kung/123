"""價量圖：只讀 snr_backtest/data OHLCV CSV，輸出 PNG（非買賣建議）。"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
import pandas as pd

SNR_DATA = Path(r"C:\Users\AUSER\Desktop\trade\snr_backtest\data")
CHART_DIR = Path(__file__).resolve().parents[1] / "static" / "charts"

for _fname in ("Microsoft JhengHei", "Microsoft YaHei", "Noto Sans CJK TC", "SimHei"):
    try:
        plt.rcParams["font.sans-serif"] = [_fname]
        plt.rcParams["axes.unicode_minus"] = False
        font_manager.FontProperties(family=_fname)
        break
    except Exception:
        continue


def _csv_path(ticker: str) -> Path | None:
    p = SNR_DATA / f"{ticker}.csv"
    if p.exists():
        return p
    code = ticker.split(".")[0]
    for cand in SNR_DATA.glob(f"{code}.*.csv"):
        return cand
    return None


def make_price_volume_chart(ticker: str, name: str = "", days: int = 60) -> dict:
    """Return {ok, path, url, error, last_close, last_date}."""
    CHART_DIR.mkdir(parents=True, exist_ok=True)
    src = _csv_path(ticker)
    if not src:
        return {"ok": False, "path": None, "url": None, "error": f"找不到行情 CSV：{ticker}"}

    df = pd.read_csv(src)
    if df.empty or "Close" not in df.columns:
        return {"ok": False, "path": None, "url": None, "error": "CSV 無收盤價"}

    df["Date"] = pd.to_datetime(df["Date"])
    df = df.sort_values("Date").tail(days).reset_index(drop=True)

    up_c, dn_c = "#e53935", "#3fb950"
    colors = [up_c if c >= o else dn_c for o, c in zip(df["Open"], df["Close"])]

    fig, (ax, axv) = plt.subplots(
        2,
        1,
        figsize=(9.2, 4.8),
        sharex=True,
        gridspec_kw={"height_ratios": [3, 1]},
        facecolor="#0e1117",
    )
    for a in (ax, axv):
        a.set_facecolor("#161b22")
        a.tick_params(colors="#8b949e")
        for spine in a.spines.values():
            spine.set_color("#30363d")

    width = 0.6
    for i, row in df.iterrows():
        ax.plot([i, i], [row["Low"], row["High"]], color=colors[i], linewidth=1)
        bottom = min(row["Open"], row["Close"])
        height = abs(row["Close"] - row["Open"]) or 0.01
        ax.add_patch(
            plt.Rectangle(
                (i - width / 2, bottom),
                width,
                height,
                facecolor=colors[i],
                edgecolor=colors[i],
                linewidth=0,
            )
        )

    title = f"{ticker} {name} · 近{days}日價量（只讀）".strip()
    ax.set_title(title, color="#e6edf3", fontsize=12, loc="left", pad=8)
    ax.set_ylabel("價格", color="#8b949e")
    last = df.iloc[-1]
    ax.annotate(
        f"收 {last['Close']:.2f}",
        xy=(len(df) - 1, last["Close"]),
        xytext=(-4, 8),
        textcoords="offset points",
        ha="right",
        color="#e6edf3",
        fontsize=9,
    )

    axv.bar(range(len(df)), df["Volume"].fillna(0), color=colors, width=0.7)
    axv.set_ylabel("量", color="#8b949e")

    n = len(df)
    step = max(1, n // 6)
    ticks = list(range(0, n, step))
    if ticks[-1] != n - 1:
        ticks.append(n - 1)
    axv.set_xticks(ticks)
    axv.set_xticklabels([df.loc[i, "Date"].strftime("%m/%d") for i in ticks], color="#8b949e")

    fig.tight_layout()
    safe = ticker.replace(".", "_")
    out = CHART_DIR / f"{safe}_pv.png"
    fig.savefig(out, dpi=120, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)

    return {
        "ok": True,
        "path": str(out),
        "url": f"/charts/{out.name}",
        "error": None,
        "last_close": float(last["Close"]),
        "last_date": str(last["Date"].date()),
    }


if __name__ == "__main__":
    print(make_price_volume_chart("5314.TWO", "世紀"))
