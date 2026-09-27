# -*- coding: utf-8 -*-
"""評測：路由正確率（不執行處理器）與回答品質（實際跑完整流程）分開算。

用法（在 D:\\trade-rag 底下）：
  .venv\\Scripts\\python.exe eval\\run_eval.py --routing        只測路由（快，約 10 秒）
  .venv\\Scripts\\python.exe eval\\run_eval.py --full           路由＋回答（會呼叫 Ollama、抓個股新聞，數分鐘）
  .venv\\Scripts\\python.exe eval\\run_eval.py --regression     交易回歸：路由＋子路徑；--compare-7860 另與正式版比對引用
結果寫到 eval/results/（json＋md），並累加到 eval/results/history.csv。
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
RESULTS = ROOT / "eval" / "results"


def load_rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["history"] = json.loads(r["history_json"]) if r.get("history_json") else []
    return rows


def check_keywords(answer: str, spec: str) -> tuple[bool, list[str]]:
    """spec：以 ; 分隔「全部都要」，每項可用 | 表示「任一即可」。空字串＝只要非空。"""
    if not spec:
        return bool(answer.strip()), []
    missing = []
    for part in spec.split(";"):
        alts = [a for a in part.split("|") if a]
        if not any(a.lower() in answer.lower() for a in alts):
            missing.append(part)
    return not missing, missing


def eval_routing(rows: list[dict]) -> list[dict]:
    from router import route

    out = []
    for r in rows:
        t0 = time.perf_counter()
        d = route(r["question"], r["history"], None)
        ms = (time.perf_counter() - t0) * 1000
        route_ok = d.route == r["expected_route"]
        sub_ok = (not r["expected_sub"]) or d.sub == r["expected_sub"]
        out.append({"id": r["id"], "category": r["category"], "question": r["question"],
                    "expected_route": r["expected_route"], "expected_sub": r["expected_sub"],
                    "route": d.route, "sub": d.sub, "stage": d.stage, "reason": d.reason,
                    "route_ok": route_ok, "sub_ok": sub_ok, "ok": route_ok and sub_ok,
                    "scores": {t: {"sim": s["sim"], "thr": s["thr"], "margin": s["margin"], "best": s["best"]}
                               for t, s in d.scores.items()},
                    "route_ms": round(ms, 1)})
    return out


def eval_full(rows: list[dict]) -> list[dict]:
    from chatbot import chat
    from textutil import has_simplified

    out = []
    for r in rows:
        res = chat(r["question"], r["history"], None, None, source="eval")
        ans = res.get("answer", "")
        kw_ok, missing = check_keywords(ans, r.get("expected_keywords", ""))
        src_ok = True
        if r.get("expected_source"):
            src_ok = any(r["expected_source"] in str(s.get("source") or s.get("title")) for s in res.get("sources", [])[:3])
        simp = has_simplified(ans) if res["route"] in ("general", "school") else False
        guard = res.get("date_guard", "")
        answer_ok = kw_ok and src_ok and not simp and not res.get("error") and res["route"] == r["expected_route"]
        out.append({"id": r["id"], "category": r["category"], "question": r["question"],
                    "expected_route": r["expected_route"], "route": res["route"], "sub": res.get("sub_route"),
                    "route_ok": res["route"] == r["expected_route"],
                    "sub_ok": (not r["expected_sub"]) or res.get("sub_route") == r["expected_sub"],
                    "answer_ok": answer_ok, "missing_keywords": missing, "source_ok": src_ok,
                    "simplified": simp, "date_guard": guard, "error": res.get("error", ""),
                    "latency_ms": res["latency_ms"]["total"], "route_ms": res["latency_ms"]["route"],
                    "model": res.get("model"), "answer": ans[:600],
                    "sources": [s.get("title") for s in res.get("sources", [])[:3]],
                    "stage": res["decision"]["stage"]})
        print(f"{r['id']} route={res['route']}/{res.get('sub_route')} ok={answer_ok} {res['latency_ms']['total']}ms",
              flush=True)
    return out


def ask_7860(q: str) -> str:
    req = urllib.request.Request("http://127.0.0.1:7860/ask", data=json.dumps({"q": q}).encode("utf-8"),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=300) as resp:
        return json.loads(resp.read().decode("utf-8")).get("answer", "")


def eval_regression(path: Path, compare: bool) -> list[dict]:
    from answer import ask
    from router import route

    rows = list(csv.DictReader(path.open(encoding="utf-8-sig", newline="")))
    out = []
    for r in rows:
        d = route(r["question"], None, None)
        rec = {"id": r["id"], "question": r["question"], "route": d.route, "sub": d.sub, "stage": d.stage,
               "route_ok": d.route == r["expected_route"], "sub_ok": d.sub == r["expected_sub"]}
        if compare and d.sub == "rules":
            new = ask(d.question)
            new_cites = [f"{h['source']} / {h['heading']}" for h in new["hits"][:3]]
            old_ans = ask_7860(r["question"])
            old_cites = [l[2:].strip() for l in old_ans.split("（引用片段）")[-1].strip().splitlines() if l.startswith("- ")]
            rec.update(new_cites=new_cites, old_cites=old_cites, cites_same=new_cites == old_cites,
                       file_ok=(not r["expected_file"]) or any(r["expected_file"] in c for c in new_cites),
                       new_answer=new["answer"][:300], old_answer=old_ans.split("（引用片段）")[0].strip()[:300])
        out.append(rec)
        print(r["id"], rec.get("route"), rec.get("sub"), rec.get("cites_same", ""), flush=True)
    return out


def summarize(kind: str, res: list[dict]) -> dict:
    s: dict = {"kind": kind, "n": len(res), "ts": datetime.now().isoformat(timespec="seconds")}
    if kind in ("routing", "full"):
        s["routing_accuracy"] = round(sum(r["route_ok"] for r in res) / len(res), 4)
        s["routing_plus_sub_accuracy"] = round(sum(r["route_ok"] and r["sub_ok"] for r in res) / len(res), 4)
        cats = sorted({r["category"] for r in res})
        s["by_category"] = {c: f"{sum(r['route_ok'] and r['sub_ok'] for r in res if r['category'] == c)}/"
                               f"{sum(1 for r in res if r['category'] == c)}" for c in cats}
        s["routing_failures"] = [f"{r['id']} {r['question']} → {r['route']}/{r.get('sub')} "
                                 f"(expected {r['expected_route']}/{r.get('expected_sub', '')})"
                                 for r in res if not (r["route_ok"] and r["sub_ok"])]
    if kind == "full":
        s["answer_pass_rate"] = round(sum(r["answer_ok"] for r in res) / len(res), 4)
        s["answer_failures"] = [f"{r['id']} {r['question']} missing={r['missing_keywords']} src_ok={r['source_ok']} "
                                f"simplified={r['simplified']} guard={r['date_guard']} err={bool(r['error'])}"
                                for r in res if not r["answer_ok"]]
        by_route: dict = {}
        for r in res:
            by_route.setdefault(r["route"], []).append(r["latency_ms"])
        s["latency_ms_by_route"] = {k: {"n": len(v), "avg": round(statistics.mean(v)), "max": max(v)}
                                    for k, v in by_route.items()}
        s["avg_route_ms"] = round(statistics.mean(r["route_ms"] for r in res), 1)
        s["models"] = sorted({str(r["model"]) for r in res if r["model"]})
    if kind == "regression":
        s["route_sub_ok"] = f"{sum(r['route_ok'] and r['sub_ok'] for r in res)}/{len(res)}"
        cmp = [r for r in res if "cites_same" in r]
        if cmp:
            s["cites_identical_vs_7860"] = f"{sum(r['cites_same'] for r in cmp)}/{len(cmp)}"
            s["expected_file_in_top3"] = f"{sum(r['file_ok'] for r in cmp)}/{len(cmp)}"
    return s


def write(kind: str, res: list[dict], summ: dict) -> Path:
    RESULTS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    p = RESULTS / f"{stamp}_{kind}.json"
    p.write_text(json.dumps({"summary": summ, "results": res}, ensure_ascii=False, indent=2), encoding="utf-8")
    (RESULTS / f"latest_{kind}.json").write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
    hist = RESULTS / "history.csv"
    new = not hist.exists()
    with hist.open("a", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["ts", "kind", "n", "routing_accuracy", "routing_plus_sub", "answer_pass_rate", "file"])
        w.writerow([summ["ts"], kind, summ["n"], summ.get("routing_accuracy", ""), summ.get("routing_plus_sub_accuracy",
                    summ.get("route_sub_ok", "")), summ.get("answer_pass_rate", ""), p.name])
    return p


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=str(ROOT / "eval" / "eval_set.csv"))
    ap.add_argument("--routing", action="store_true")
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--regression", action="store_true")
    ap.add_argument("--compare-7860", action="store_true")
    ap.add_argument("--only", default="", help="逗號分隔的 id，只跑這些")
    a = ap.parse_args()
    if a.regression:
        res = eval_regression(ROOT / "eval" / "trade_regression.csv", a.compare_7860)
        summ = summarize("regression", res)
    else:
        rows = load_rows(Path(a.csv))
        if a.only:
            keep = set(a.only.split(","))
            rows = [r for r in rows if r["id"] in keep]
        if a.full:
            res = eval_full(rows)
            summ = summarize("full", res)
        else:
            res = eval_routing(rows)
            summ = summarize("routing", res)
    p = write(summ["kind"], res, summ)
    print(json.dumps(summ, ensure_ascii=False, indent=2))
    print("wrote", p)


if __name__ == "__main__":
    main()
