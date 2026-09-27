"""timetable/eligibility.py — 「這個學生能不能修這門課？」（限修檢查）

把前端 core.js 的 S.canTake(c) 翻成 Python，前後端判斷一致。
輸入：restr（CourseRestriction.to_front() 的縮寫 dict）與 student（accounts 的 profile dict）
輸出：{"ok": bool, "reasons": [中文原因], "tags": [{"t": 標籤, "bad": bool}], "unknown": bool}
"""
import re
import unicodedata

CN = ["", "一", "二", "三", "四", "五", "六", "七"]


def nf(x):
    return re.sub(r"\s", "", unicodedata.normalize("NFKC", str(x or "")))


def dept_match(rule, dept):
    """「中文系」≈「中國文學系」、「資科系」≈「資料科學系」：簡稱的字依序出現在全名中"""
    a, b = nf(rule), nf(dept)
    if not a or not b:
        return False
    if a == b or b in a or a in b:
        return True
    sa = re.sub(r"學?系$", "", a)
    i = 0
    for ch in b:
        if i < len(sa) and ch == sa[i]:
            i += 1
    return len(sa) >= 2 and i == len(sa)


def can_take(restr, student):
    reasons, tags = [], []
    if not restr:
        return {"ok": True, "reasons": reasons, "tags": tags, "unknown": True}
    grade = int(student.get("grade") or 0)
    g = restr.get("g")
    if g:
        bad = grade not in g
        t = "限 " + "、".join(CN[x] if isinstance(x, int) and x < len(CN) else str(x) for x in g) + " 年級"
        tags.append({"t": t, "bad": bad})
        if bad:
            reasons.append(f"{t}（你是 {grade} 年級）")
    elif restr.get("min"):
        bad = grade < restr["min"]
        t = f"限 {restr['min']} 年級以上"
        tags.append({"t": t, "bad": bad})
        if bad:
            reasons.append(f"{t}（你是 {grade} 年級）")
    if restr.get("p"):
        bad = not any(nf(x) == nf(student.get("program")) for x in restr["p"])
        t = "限" + "、".join(restr["p"])
        tags.append({"t": t, "bad": bad})
        if bad:
            reasons.append(f"{t}（你是{student.get('program')}）")
    if restr.get("d"):
        bad = not any(dept_match(x, student.get("dept")) for x in restr["d"])
        t = "限" + "、".join(restr["d"])
        tags.append({"t": t, "bad": bad})
        if bad:
            reasons.append(f"{t}（你是{student.get('dept')}）")
    if restr.get("c"):
        mine = student.get("classLabel") or ""
        bad = not (mine and any(nf(x) == nf(mine) for x in restr["c"]))
        t = "限" + "、".join(restr["c"])
        tags.append({"t": t, "bad": bad})
        if bad:
            reasons.append(t)
    x = restr.get("x") or ""
    if re.search(r"限重.?補修", x):
        tags.append({"t": "限重補修生", "bad": True})
        reasons.append("限重補修生（一般修課不適用）")
    excl = restr.get("dn")
    if not excl:
        m = re.search(r"不可選\s*學系:([^；]+)", x)
        excl = [s.strip() for s in re.split(r"[,，、]", m.group(1)) if s.strip()] if m else None
    if excl:
        bad = any(dept_match(d, student.get("dept")) for d in excl)
        t = "、".join(excl) + "不可選"
        tags.append({"t": t, "bad": bad})
        if bad:
            reasons.append(f"{t}（你是{student.get('dept')}）")
    if "不得加選" in x:
        tags.append({"t": "開學後不開放加選", "bad": True})
        reasons.append("學校設定開學後不得加選")
    return {"ok": not reasons, "reasons": reasons, "tags": tags, "unknown": not restr.get("chk"),
            "exceptions": restr.get("e") or [], "other": x}
