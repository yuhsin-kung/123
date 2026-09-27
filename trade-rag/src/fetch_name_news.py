"""On-demand name news fetch via snr_backtest news_risk.name_heat (writes paper/name_news only)."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

SNR_ROOT = Path(r"C:\Users\AUSER\Desktop\trade\snr_backtest")
SNR_PY = SNR_ROOT / ".venv" / "Scripts" / "python.exe"
NAME_NEWS = SNR_ROOT / "paper" / "name_news"


def _latest_cache(ticker: str) -> dict | None:
    if not NAME_NEWS.exists():
        return None
    key = ticker.replace(".", "_")
    files = sorted(NAME_NEWS.glob(f"*_{key}.json"))
    if not files:
        code = ticker.split(".")[0]
        files = sorted(NAME_NEWS.glob(f"*{code}*.json"))
    if not files:
        return None
    return json.loads(files[-1].read_text(encoding="utf-8"))


def fetch_name_news_live(ticker: str, name: str, timeout: int = 90) -> dict:
    """Run name_heat (writes UTF-8 cache), then read the cache file back.

    Do not trust subprocess stdout for Chinese: on Windows the child may print
    cp950 while we expect UTF-8, which mojibake-corrupts titles in the UI.
    """
    if not SNR_PY.exists():
        raise FileNotFoundError(f"missing {SNR_PY}")
    code = (
        "import json,sys\n"
        "sys.path.insert(0, r'C:\\Users\\AUSER\\Desktop\\trade\\snr_backtest')\n"
        "from news_risk import name_heat\n"
        "ticker, name = sys.argv[1], sys.argv[2]\n"
        "name_heat(ticker, name)\n"
        "print('OK')\n"
    )
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run(
        [str(SNR_PY), "-c", code, ticker, name or ""],
        cwd=str(SNR_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        env=env,
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "fetch failed")[-800:])
    cached = _latest_cache(ticker)
    if not cached:
        raise RuntimeError("name_heat finished but name_news cache missing")
    return cached
