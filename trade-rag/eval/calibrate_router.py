# -*- coding: utf-8 -*-
"""在標註評測集上校準「每個 store 自己的門檻」（不比較不同 store 的原始分數）。

只有走到「打分」階段的題目會受門檻影響（規則命中的題目，例如股票實體、課表關鍵字，不受影響），
所以只用這些題目做網格搜尋：
  thr_trade, thr_school, thr_general ∈ [0.30, 0.80]，clarify_gap ∈ {0.00…0.08}，cont_bias 固定 0.10
目標：路由正確率最高；同分的組合很多時，取「最佳組合區域的中心」（離邊界最遠 → 比較穩）。
另外做 leave-one-out（每次拿掉一題校準、再測那一題）估計「沒看過的題目」大概的正確率。

用法：  .venv\\Scripts\\python.exe eval\\calibrate_router.py [--write]
--write 會把結果寫進 data/router/thresholds.json（router.py 會自動重新讀取）。
"""
from __future__ import annotations

import argparse
import itertools
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "eval"))

from config import ROUTER_THRESHOLDS  # noqa: E402
from run_eval import load_rows  # noqa: E402
import router as R  # noqa: E402

SCORING_STAGES = {"scores", "continuation", "vague", "llm_fallback"}
GRID = np.round(np.arange(0.30, 0.801, 0.02), 2)
GAPS = [0.0, 0.02, 0.04, 0.06, 0.08]
CONT = 0.10


def collect(rows):
    thr0 = dict(R.DEFAULT_THRESHOLDS)
    items = []
    for r in rows:
        d = R._route(r["question"], r["history"], None, thr0)
        sims = R.store_sims(r["question"])
        items.append({"id": r["id"], "q": r["question"], "exp": r["expected_route"], "stage": d.stage,
                      "scoring": d.stage in SCORING_STAGES, "sims": sims, "prev": d.prev_topic,
                      "followup": d.followup, "vague": R.is_vague(r["question"]), "fixed_route": d.route})
    return items


def simulate(it, thr):
    topic, *_ = R.decide_from_sims(it["sims"], thr, it["prev"], it["followup"])
    if topic == "general" and not it["followup"] and it["vague"]:
        return "clarify"
    return topic


def accuracy(items, thr):
    return sum(simulate(it, thr) == it["exp"] for it in items)


def search(items, grid=GRID, gaps=GAPS):
    best, combos = -1, []
    for tt, ts, tg, gap in itertools.product(grid, grid, grid, gaps):
        thr = {"trade": tt, "school": ts, "general": tg, "clarify_gap": gap, "cont_bias": CONT}
        a = accuracy(items, thr)
        if a > best:
            best, combos = a, [(tt, ts, tg, gap)]
        elif a == best:
            combos.append((tt, ts, tg, gap))
    arr = np.array(combos)
    center = arr.mean(axis=0)
    pick = arr[np.argmin(((arr - center) ** 2).sum(axis=1))]
    return best, {"trade": float(pick[0]), "school": float(pick[1]), "general": float(pick[2]),
                  "clarify_gap": float(pick[3]), "cont_bias": CONT}, len(combos)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--csv", default=str(ROOT / "eval" / "eval_set.csv"))
    a = ap.parse_args()
    rows = load_rows(Path(a.csv))
    items = collect(rows)
    sc = [it for it in items if it["scoring"]]
    print(f"{len(items)} 題，其中 {len(sc)} 題走到打分階段（其餘由規則決定，不受門檻影響）")
    for it in sc:
        s = it["sims"]
        print(f"  {it['id']:4} exp={it['exp']:8} trade={s['trade']['sim']:.3f} school={s['school']['sim']:.3f} "
              f"general={s['general']['sim']:.3f}  {it['q']}")
    base = accuracy(sc, dict(R.DEFAULT_THRESHOLDS))
    best, thr, n = search(sc)
    print(f"預設門檻 {R.DEFAULT_THRESHOLDS} → 打分題正確 {base}/{len(sc)}")
    print(f"校準後   {thr} → 打分題正確 {best}/{len(sc)}（{n} 組並列最佳，取中心）")
    # leave-one-out（粗網格）
    coarse = np.round(np.arange(0.30, 0.801, 0.04), 2)
    loo = 0
    for i, it in enumerate(sc):
        rest = sc[:i] + sc[i + 1:]
        _, t_i, _ = search(rest, coarse, [0.0, 0.04, 0.08])
        loo += simulate(it, t_i) == it["exp"]
    print(f"leave-one-out（沒看過該題時）打分題正確 {loo}/{len(sc)}")
    wrong = [f"{it['id']} {it['q']} → {simulate(it, thr)} (exp {it['exp']})" for it in sc if simulate(it, thr) != it["exp"]]
    for w in wrong:
        print("  仍錯：", w)
    out = {"thresholds": thr, "calibrated_at": datetime.now().isoformat(timespec="seconds"),
           "eval_csv": Path(a.csv).name, "scoring_items": len(sc), "scoring_correct": best,
           "scoring_correct_default": base, "loo_correct": loo, "tied_best_combos": n,
           "method": "per-store threshold grid search on labelled eval; margin = sim - thr; center of tied-best region"}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    if a.write:
        ROUTER_THRESHOLDS.parent.mkdir(parents=True, exist_ok=True)
        ROUTER_THRESHOLDS.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print("wrote", ROUTER_THRESHOLDS)


if __name__ == "__main__":
    main()
