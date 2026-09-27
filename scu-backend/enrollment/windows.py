"""enrollment/windows.py — 從行事曆資料推算「選課時段」，並判斷現在能不能加選／退選

資料來源：events.Event（category="選課"）。主要用「學士班網路選課註冊時間表」(source=scu_course_timetable)，
它的 raw_text 中間欄有時間，例如：
    "17 日 | 9:00 24:00 | 初選：網路登記選課（不含第二專長課程）"   → 6/17 09:00 ～ 7/2 24:00
    "18 日 | 20:00 16:00 | 開學後加退選④：全校所有課程"            → 9/18 20:00 ～ 9/21 16:00
沒有時間表時，退回行事曆 ICS 的「加退選」整天事件。

每個時段（Window）有：
  kind          select＝可加選也可退選、drop＝只能退選、confirm＝只能確認清單（不能加退選）
  course_scope  all＝全部課程、major＝只限學系專業課程、general＝只限共通（通識／體育…）課程
  applies       這個時段適不適用目前學生（例如「新生網路選課」「理學院各系…」不適用資科三）
"""
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, time, timedelta

from django.conf import settings

from events.models import Event
from timetable.models import GENERAL_DEPTS

from .clock import TZ

# 學院簡稱：時間表寫「巨量學院各系」「人社院」這種簡稱
COLLEGE_ALIASES = {
    "巨量資料管理學院": ["巨量學院", "巨量"],
    "理學院": ["理學院"],
    "商學院": ["商學院"],
    "人文社會學院": ["人社院", "人社學院"],
    "外國語文學院": ["外語學院"],
    "法學院": ["法學院", "法律系"],
}
ALL_SCOPE_TOKENS = sorted({t for v in COLLEGE_ALIASES.values() for t in v}, key=len, reverse=True)
# 「共通科目」：通識類＋國文、外文、體育、全校選修（依班級課表的系所類別判斷）
COMMON_DEPTS = set(GENERAL_DEPTS) | {"國文", "外文", "體育", "全校選修", "補救課程"}
SKIP_WORDS = ("人工加選", "結果查詢", "列印", "導師輔導", "公告選課", "線上登記", "抵免")
TIME_RE = re.compile(r"(\d{1,2})\s*[:：]\s*(\d{2})")
WD = "一二三四五六日"


@dataclass
class Window:
    title: str
    start: datetime
    end: datetime
    kind: str                  # select / drop / confirm
    phase: str                 # 初選 / 加退選 / 新生選課 / 退選 / 確認清單
    course_scope: str = "all"  # all / major / general / second
    applies: bool = True
    why_not: str = ""
    source: str = ""
    event_id: int = 0
    notes: list = field(default_factory=list)

    def contains(self, now):
        return self.start <= now < self.end

    def label(self):
        return f"{self.title}（{fmt_range(self.start, self.end)}）"

    def to_json(self, now=None):
        d = asdict(self)
        d["start"], d["end"] = self.start.isoformat(), self.end.isoformat()
        d["range"] = fmt_range(self.start, self.end)
        d["canAdd"] = self.kind == "select"
        d["canDrop"] = self.kind in ("select", "drop")
        if now is not None:
            d["status"] = "open" if self.contains(now) else ("upcoming" if now < self.start else "ended")
        return d


def fmt_dt(d, is_end=True):
    """結束時間 00:00 顯示成「前一天 24:00」（學校時間表的寫法）"""
    if is_end and d.hour == 0 and d.minute == 0:
        prev = d - timedelta(minutes=1)
        return f"{prev.month}/{prev.day}（{WD[prev.weekday()]}）24:00"
    return f"{d.month}/{d.day}（{WD[d.weekday()]}）{d:%H:%M}"


def fmt_range(a, b):
    return f"{fmt_dt(a, is_end=False)} ～ {fmt_dt(b)}"


def _times(raw):
    """raw_text 中間欄的起訖時間；沒有就整天。'24:00' → 隔天 00:00"""
    parts = (raw or "").split("|")
    mid = parts[1] if len(parts) >= 3 else ""
    ts = [(int(h), int(m)) for h, m in TIME_RE.findall(mid)]
    start = ts[0] if ts else (0, 0)
    end = ts[1] if len(ts) >= 2 else (24, 0)
    return start, end


def _at(d, hm):
    h, m = hm
    base = datetime.combine(d, time(0, 0), tzinfo=TZ)
    return base + timedelta(hours=h, minutes=m)


def _classify(title):
    """標題 → (kind, phase, course_scope)；不是線上選課階段回 None"""
    if any(w in title for w in SKIP_WORDS):
        return None
    if "確認選課清單" in title:
        return "confirm", "確認清單", "all"
    if "即時退選" in title:
        return "drop", "退選", "all"
    if "初選" in title:
        return "select", "初選", "all"
    if "第二專長" in title and "共通" not in title and "加退選" not in title:
        return "select", "第二專長選課", "second"
    if "加退選" in title or "選課" in title:
        phase = "新生選課" if "新生" in title else "加退選"
        if "共通科目" in title:
            scope = "general"
        elif "專業課程" in title and "全校所有課程" not in title:
            scope = "major"
        else:
            scope = "all"
        return "select", phase, scope
    return None


def _applies(title, student, scope):
    """這個時段適用這個學生嗎？回傳 (bool, 不適用原因)"""
    if "新生" in title and int(student.get("grade") or 0) != 1:
        return False, "只限新生"
    if scope == "second":
        return False, "只限第二專長課程（本示範未區分第二專長）"
    tokens = [t for t in ALL_SCOPE_TOKENS if t in title]
    if tokens:
        mine = COLLEGE_ALIASES.get(student.get("college") or "", []) + [student.get("dept") or ""]
        if not any(m and m in title for m in mine):
            return False, "只限" + "、".join(tokens) + "的學生"
    return True, ""


def selection_windows(student, semester=None):
    """回傳這學期所有選課相關時段（含不適用的，前端可以灰色顯示）"""
    semester = semester or settings.SCU_SEMESTER
    qs = Event.objects.filter(category="選課", is_active=True, semester=semester)
    rows = list(qs.filter(source_name="scu_course_timetable").order_by("start_date", "id"))
    source = "學士班網路選課註冊時間表"
    if not rows:  # 沒有時間表 → 用行事曆 ICS 的「加退選」「選課」
        rows = list(qs.filter(source_name="scu_calendar_ics").order_by("start_date", "id"))
        source = "東吳大學行事曆"
    out = []
    for e in rows:
        c = _classify(e.title)
        if not c:
            continue
        kind, phase, scope = c
        (sh, sm), (eh, em) = _times(e.raw_text)
        start = _at(e.start_date, (sh, sm))
        end = _at(e.end_date or e.start_date, (eh, em))
        if end <= start:                           # 保險：時間解析怪怪的就當整天
            end = _at(e.end_date or e.start_date, (24, 0))
        ok, why = _applies(e.title, student, scope)
        out.append(Window(e.title, start, end, kind, phase, scope, ok, why, source, e.pk))
    out.sort(key=lambda w: (w.start, w.end))
    return out


SCOPE_TEXT = {"all": "全部課程", "major": "學系專業課程", "general": "共通科目（通識、體育等）", "second": "第二專長課程"}


def window_status(student, now, semester=None):
    """現在的選課狀態。回傳 dict（/api/selection/window 直接輸出）"""
    wins = selection_windows(student, semester)
    usable = [w for w in wins if w.applies]
    active = [w for w in usable if w.contains(now)]
    select = [w for w in active if w.kind == "select"]
    drop = [w for w in active if w.kind == "drop"]
    confirm = [w for w in active if w.kind == "confirm"]
    can_add = bool(select)
    can_drop = bool(select or drop)
    scopes = sorted({w.course_scope for w in select})
    if "all" in scopes:
        scopes = ["all"]
    upcoming = [w for w in usable if w.start > now and w.kind in ("select", "drop")]
    ended = [w for w in usable if w.end <= now and w.kind in ("select", "drop")]
    nxt, last = (upcoming[0] if upcoming else None), (ended[-1] if ended else None)
    now_txt = f"{now:%Y/%m/%d} {now:%H:%M}"
    if can_add:
        cur = select[0]
        reason = f"現在是「{cur.title}」（{fmt_range(cur.start, cur.end)}），可以加選與退選"
        if scopes != ["all"]:
            reason += "；這個階段只開放" + "、".join(SCOPE_TEXT[s] for s in scopes)
    elif can_drop:
        cur = drop[0]
        reason = f"現在是「{cur.title}」（{fmt_range(cur.start, cur.end)}），只能退選、不能加選"
    else:
        reason = f"目前（示範時間 {now_txt}）不是選課時段，不能加選、退選或送出選課。"
        if confirm:
            reason += f"現在是「{confirm[0].title}」（{fmt_range(confirm[0].start, confirm[0].end)}），只能確認選課清單。"
        if last:
            reason += f"上一個選課時段「{last.title}」已於 {fmt_dt(last.end)} 結束。"
        reason += f"下一個選課時段：「{nxt.title}」{fmt_range(nxt.start, nxt.end)}。" if nxt else "下一個選課時段尚未公布。"
    return {"now": now.isoformat(), "semester": semester or settings.SCU_SEMESTER, "open": can_add or can_drop,
            "canAdd": can_add, "canDrop": can_drop, "courseScopes": scopes if can_add else [],
            "phase": (select or drop or confirm or [None])[0].to_json(now) if (select or drop or confirm) else None,
            "reason": reason, "next": nxt.to_json(now) if nxt else None, "last": last.to_json(now) if last else None,
            "windows": [w.to_json(now) for w in wins], "_active": active, "_select": select}


def course_in_scope(course, scopes):
    """課程是否屬於這個階段開放的範圍（general＝通識類系所的課；major＝其他）"""
    if not scopes or "all" in scopes:
        return True
    is_general = bool(course.get("general")) or course.get("dept") in COMMON_DEPTS
    return ("general" in scopes and is_general) or ("major" in scopes and not is_general)
