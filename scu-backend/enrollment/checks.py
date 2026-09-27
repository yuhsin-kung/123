"""enrollment/checks.py — 送出前檢查（伺服器端）：衝堂、學分、額滿（模擬）、限修

與前端 core.js 的 S.runChecks() 規則相同，但這裡是「伺服器說了算」：
就算有人繞過網頁直接 POST，也一樣會被擋下來。
"""
from django.conf import settings

from timetable.eligibility import can_take

from .seats import remain

WK_PAIR = {"單": "雙", "雙": "單", "前": "後", "後": "前"}
WD = "一二三四五六日"
PLABEL = "1234E56789ABCD"


def overlap(a, b):
    """兩門課重疊的時段（單週 vs 雙週、前 9 週 vs 後 9 週 不算衝堂；時段保留列不算）"""
    out = []
    if a["placeholder"] or b["placeholder"]:
        return out
    for x in a["slots"]:
        for y in b["slots"]:
            if x["wk"] and WK_PAIR.get(x["wk"]) == y["wk"]:
                continue
            if x["day"] == y["day"] and x["start"] <= y["end"] and y["start"] <= x["end"]:
                out.append({"day": x["day"], "from": max(x["start"], y["start"]), "to": min(x["end"], y["end"])})
    return out


def slot_text(o):
    wd = WD[o["day"] - 1] if 1 <= o["day"] <= 7 else "?"
    a, b = PLABEL[o["from"] - 1], PLABEL[o["to"] - 1]
    return f"星期{wd} 第 {a}{'' if a == b else '–' + b} 節"


def credits_of(courses):
    return sum(0 if c["placeholder"] else c["credits"] for c in courses)


def run_checks(planned, adds, student, delta):
    """planned：送出後的課表（課程 dict 清單）；adds：這次要加選的課（不含本來就在課表上的）"""
    rule = settings.SCU_CREDIT_RULE
    messages, conflicts, full, restricted = [], [], [], []
    for i in range(len(planned)):
        for j in range(i + 1, len(planned)):
            ov = overlap(planned[i], planned[j])
            if ov:
                a, b = planned[i], planned[j]
                conflicts.append({"a": a["code"], "b": b["code"], "overlap": ov})
                messages.append(f"衝堂：「{a['name']}」({a['no'] or a['code']}) 與「{b['name']}」({b['no'] or b['code']}) "
                                f"在{slot_text(ov[0])}時間重疊")
    add_codes = {c["code"] for c in adds}
    for c in adds:
        if remain(c, delta) <= 0:
            full.append(c["code"])
            messages.append(f"額滿：「{c['name']}」({c['no']}) 人數上限 {c['cap']} 人已滿（已選人數為模擬數字）")
        if c.get("specialBlocking"):
            restricted.append({"code": c["code"], "reasons": [c["special"][1] if c.get("special") else "特殊課程"]})
            messages.append(f"特殊課程：「{c['name']}」({c['no']})：" + (c["special"][1] if c.get("special") else "一般選課不能直接選"))
        k = can_take(c["restr"], student)
        if not k["ok"]:
            restricted.append({"code": c["code"], "reasons": k["reasons"]})
            messages.append(f"限修不符：「{c['name']}」({c['no']})：" + "；".join(k["reasons"]))
    credits = credits_of(planned)
    issue = "low" if credits < rule["min"] else "high" if credits > rule["max"] else ""
    if issue == "low":
        messages.append(f"學分不足：送出後共 {credits:g} 學分，低於下限 {rule['min']} 學分（示範規則）")
    elif issue == "high":
        messages.append(f"學分超過：送出後共 {credits:g} 學分，超過上限 {rule['max']} 學分（示範規則）")
    return {"ok": not messages, "credits": credits, "creditRule": rule, "creditIssue": issue,
            "conflicts": conflicts, "full": full, "restricted": restricted, "messages": messages,
            "planned": [c["code"] for c in planned], "adds": sorted(add_codes)}
