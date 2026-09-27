"""enrollment/tests.py — 選課檢查與「選課時段鎖定」的自動測試

執行：python manage.py test
每個測試都用一個全新的空資料庫（Django 自動建立、測完刪掉），資料在 setUpTestData 裡自己造，
所以不需要先匯入全校課程，也不會動到你的 db.sqlite3。

測到的重點：
  * 不在選課時段直接 POST /api/cart 或 /api/cart/submit → 403＋中文原因（就算繞過網頁也擋得住）
  * 「只能退選」時段、時段之間的空檔、只開放學系專業／共通科目的階段、限定學院的時段
  * 衝堂（單雙週不算）、學分 16–25、額滿（模擬人數）、限修 → 409＋中文原因
  * 送出成功 → 課表更新、選課車清空、模擬已選人數 +1
"""
import json
from datetime import date, datetime, time
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import StudentProfile
from events.models import Event
from timetable.catalog import clear_cache, fake_enrolled
from timetable.eligibility import can_take, dept_match
from timetable.models import (ClassCourse, Course, CourseRestriction, CourseSession, Department, Program,
                              SchoolClass)

from .clock import TZ, demo_now
from .models import CartItem, DemoClock, Enrollment, Submission
from .windows import _times, selection_windows

SEM = "115-1"
OPEN = "2026-09-17T21:00"        # 開學後加退選③：全校所有課程
CLOSED = "2026-09-30T10:30"      # 預設示範時間：加退選已結束
DROP_ONLY = "2026-09-22T10:00"   # 網路即時退選
GAP = "2026-09-18T17:00"         # ③ 16:00 結束、④ 20:00 才開始
MAJOR_ONLY = "2026-09-14T21:00"  # 開學後加退選①：學系專業課程


def find_full_code():
    """找一個「模擬人數剛好額滿」的選課編號（fake_enrolled == cap）"""
    for n in range(9000, 9999):
        if fake_enrolled(str(n), 50) == 50:
            return str(n)
    raise AssertionError("no full code")


FULL = find_full_code()


class EnrollmentTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        now = timezone.now()
        common = dict(semester=SEM, scraped_at=now)
        prog = Program.objects.create(code="1", form_value="1學士班", label="學士班", **common)
        ds = Department.objects.create(program=prog, form_value="7373資料科學系", label="資料科學系", class_key="173", **common)
        gen = Department.objects.create(program=prog, form_value="9999通識", label="通識", class_key="199", **common)
        cls.my_class = SchoolClass.objects.create(department=ds, form_value="717332資科三Ｂ", label="資科三B", grade=3,
                                                  section="B", timetable_scraped_at=now, **common)
        gen_class = SchoolClass.objects.create(department=gen, form_value="GE", label="通識", grade=None, section="",
                                               timetable_scraped_at=now, **common)

        def course(no, name, credits, sessions, cap=60, klass=None, req="選", code=None):
            c = Course.objects.create(course_code=code or f"BDD{no}", selection_no=no, offering_key=no, name=name,
                                      offering_class=(klass or cls.my_class).label, credits=Decimal(credits),
                                      hours=Decimal(credits), capacity=cap, teacher="測試老師", **common)
            for wd, periods, wk in sessions:
                CourseSession.objects.create(course=c, weekday=wd, periods=periods, week_type=wk, room="H101")
            ClassCourse.objects.create(school_class=klass or cls.my_class, course=c, req_elective=req)
            return c

        # 已選上的 6 門（18 學分），時段互不衝突
        seeded = [course("1001", "資料探勘導論", 3, [(2, "67", "")], req="必"),
                  course("1011", "資料庫", 3, [(1, "12", "")], req="必"),
                  course("1012", "統計", 3, [(1, "34", "")], req="必"),
                  course("1013", "演算法", 3, [(3, "12", "")], req="必"),
                  course("1014", "作業系統", 3, [(5, "12", "")], req="必"),
                  course("1015", "英文", 3, [(5, "34", "")], req="必")]
        course("1002", "機器學習", 3, [(2, "67", "")])                 # 跟 1001 衝堂（星期二 6–7 節）
        course("1003", "單週課", 2, [(4, "67", "單")])                 # 1003 單週 vs 1004 雙週：不衝堂
        course("1004", "雙週課", 2, [(4, "67", "雙")])
        course("1006", "大一限定", 2, [(4, "12", "")], code="BDD10601")
        CourseRestriction.objects.create(course_code="BDD10601", grades=[1], source="selrule", rules_checked=True, **common)
        course("1007", "通識：哲學", 2, [(3, "89", "")], klass=gen_class)  # 通識類（general）
        course("1008", "超大學分", 10, [(6, "12", "")])                  # 18 + 10 = 28 > 25
        course(FULL, "熱門課", 2, [(3, "34", "")], cap=50)              # 模擬人數額滿
        Course.objects.create(course_code="BDC99713", selection_no="", offering_key="BDC99713@資科三B",
                              name="通識課程(三)", credits=2, **common)   # 時段保留列（沒有選課編號）

        def ev(title, d1, d2, times):
            Event.objects.create(source_name="scu_course_timetable", uid=title, title=title, category="選課",
                                 start_date=d1, end_date=d2, raw_text=f"x | {times} | {title}", hash="h",
                                 semester=SEM, fetched_at=now)
        ev("理學院各系專業課程網路即時加退選", date(2026, 9, 3), date(2026, 9, 4), "9:00 21:00")
        ev("人社院、外語學院、巨量學院各系專業課程網路即時加退選", date(2026, 9, 7), date(2026, 9, 8), "9:00 21:00")
        ev("開學後加退選①：學系專業課程", date(2026, 9, 14), date(2026, 9, 15), "20:00 16:00")
        ev("開學後加退選③：全校所有課程", date(2026, 9, 17), date(2026, 9, 18), "20:00 16:00")
        ev("開學後加退選④：全校所有課程", date(2026, 9, 18), date(2026, 9, 21), "20:00 16:00")
        ev("網路即時退選", date(2026, 9, 22), None, "9:00~24：00")
        ev("辦理系統無法處理之人工加選", date(2026, 9, 23), None, "9:00~19:00")
        ev("上網確認選課清單", date(2026, 10, 1), date(2026, 10, 8), "")

        cls.user = get_user_model().objects.create_user("demo", password="demo1234")
        StudentProfile.objects.create(user=cls.user, name="王小明", student_id="11316025", program="學士班",
                                      dept="資料科學系", college="巨量資料管理學院", grade=3, cls="B")
        Enrollment.objects.bulk_create([Enrollment(user=cls.user, semester=SEM, course_key=c.offering_key,
                                                   source="seed") for c in seeded])

    def setUp(self):
        clear_cache()

    # ---- 小工具 ----
    def add(self, code, action="add", **extra):
        return self.client.post("/api/cart", data=json.dumps({"code": code, "action": action}),
                                content_type="application/json", **extra)

    def submit(self):
        return self.client.post("/api/cart/submit")

    def tt(self):
        return set(Enrollment.objects.filter(user=self.user).values_list("course_key", flat=True))


@override_settings(SCU_DEMO_NOW=CLOSED)
class WindowLockTests(EnrollmentTestBase):
    def test_default_demo_now_is_closed(self):
        with override_settings(SCU_DEMO_NOW="2026-09-30T10:30"):
            self.assertEqual(demo_now(), datetime(2026, 9, 30, 10, 30, tzinfo=TZ))
            w = self.client.get("/api/selection/window").json()
        self.assertFalse(w["open"])
        self.assertFalse(w["canAdd"])
        self.assertIn("不是選課時段", w["reason"])
        self.assertIn("網路即時退選", w["reason"])        # 告訴使用者上一個時段是什麼

    def test_direct_post_add_while_closed_is_403_with_chinese_reason(self):
        r = self.add("1003")
        self.assertEqual(r.status_code, 403)
        body = r.json()
        self.assertEqual(body["error"], "selection_closed")
        self.assertIn("不是選課時段", body["reason"])
        self.assertFalse(CartItem.objects.exists())

    def test_direct_post_drop_while_closed_is_403(self):
        self.assertEqual(self.add("1011", "drop").status_code, 403)

    def test_submit_while_closed_is_403_even_if_cart_was_filled_earlier(self):
        CartItem.objects.create(user=self.user, semester=SEM, course_key="1003", action="add")  # 時段內放進去的
        before = self.tt()
        r = self.submit()
        self.assertEqual(r.status_code, 403)
        self.assertIn("選課時段", r.json()["reason"])
        self.assertEqual(self.tt(), before)                          # 課表沒有被改
        self.assertEqual(Submission.objects.get().status_code, 403)  # 被擋也有紀錄

    def test_client_supplied_time_cannot_unlock(self):
        """?at= 只能預覽 /api/selection/window，不能用來解鎖 POST"""
        self.assertTrue(self.client.get(f"/api/selection/window?at={OPEN}").json()["canAdd"])
        r = self.client.post(f"/api/cart?at={OPEN}", data=json.dumps({"code": "1003", "at": OPEN}),
                             content_type="application/json")
        self.assertEqual(r.status_code, 403)

    def test_cart_delete_is_always_allowed(self):
        CartItem.objects.create(user=self.user, semester=SEM, course_key="1003", action="add")
        r = self.client.delete("/api/cart?code=1003")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(CartItem.objects.exists())

    @override_settings(SCU_DEMO_NOW=GAP)
    def test_gap_between_add_drop_rounds_is_closed(self):
        r = self.add("1003")
        self.assertEqual(r.status_code, 403)
        self.assertIn("開學後加退選④", r.json()["reason"])        # 提示下一個時段

    @override_settings(SCU_DEMO_NOW=DROP_ONLY)
    def test_drop_only_phase(self):
        r = self.add("1003")
        self.assertEqual(r.status_code, 403)
        self.assertIn("只能退選", r.json()["reason"])
        self.assertEqual(self.add("1015", "drop").status_code, 200)

    @override_settings(SCU_DEMO_NOW=MAJOR_ONLY)
    def test_major_only_phase_rejects_general_course(self):
        r = self.add("1007")
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json()["error"], "course_not_open_in_phase")
        self.assertIn("學系專業課程", r.json()["reason"])
        self.assertEqual(self.add("1003").status_code, 200)

    def test_college_scoped_windows(self):
        with override_settings(SCU_DEMO_NOW="2026-09-07T10:00"):   # 巨量學院各系 → 資料科學系適用
            self.assertTrue(self.client.get("/api/selection/window").json()["canAdd"])
        with override_settings(SCU_DEMO_NOW="2026-09-03T10:00"):   # 理學院各系 → 不適用
            w = self.client.get("/api/selection/window").json()
            self.assertFalse(w["canAdd"])
            sci = next(x for x in w["windows"] if x["title"].startswith("理學院"))
            self.assertFalse(sci["applies"])

    def test_admin_demo_clock_overrides_settings(self):
        DemoClock.objects.create(enabled=True, now=datetime(2026, 9, 17, 21, 0, tzinfo=TZ))
        self.assertEqual(self.add("1003").status_code, 200)

    def test_window_times_parsed_from_timetable_raw_text(self):
        self.assertEqual(_times("18 日 | 20:00 16:00 | 開學後加退選④"), ((20, 0), (16, 0)))
        self.assertEqual(_times("22 日 9:00~24：00 網路即時退選 | 9:00~24：00 | 網路即時退選"), ((9, 0), (24, 0)))
        profile = {"grade": 3, "dept": "資料科學系", "college": "巨量資料管理學院"}
        w4 = next(w for w in selection_windows(profile) if "④" in w.title)
        self.assertEqual(w4.start, datetime(2026, 9, 18, 20, 0, tzinfo=TZ))
        self.assertEqual(w4.end, datetime(2026, 9, 21, 16, 0, tzinfo=TZ))
        self.assertFalse(any("人工加選" in w.title for w in selection_windows(profile)))  # 人工加選不是線上時段


@override_settings(SCU_DEMO_NOW=OPEN)
class CheckTests(EnrollmentTestBase):
    def test_conflict_is_409(self):
        r = self.add("1002")
        self.assertEqual(r.status_code, 200)                         # 可以先放進選課車
        self.assertIn("衝堂", " ".join(r.json()["checks"]["messages"]))  # 但會先提醒
        r = self.submit()
        self.assertEqual(r.status_code, 409)
        self.assertIn("衝堂", r.json()["reason"])
        self.assertIn("星期二", r.json()["reason"])
        self.assertNotIn("1002", self.tt())

    def test_single_and_double_week_do_not_conflict_and_submit_succeeds(self):
        self.add("1003")
        self.add("1004")
        r = self.submit()
        self.assertEqual(r.status_code, 200, r.content.decode())
        self.assertEqual(r.json()["credits"], 22)
        self.assertTrue({"1003", "1004"} <= self.tt())
        self.assertFalse(CartItem.objects.exists())
        e = Enrollment.objects.get(user=self.user, course_key="1003")
        self.assertEqual(e.source, "submit")
        # 模擬已選人數 +1
        c = self.client.get("/api/courses/1003").json()
        self.assertEqual(c["enrolled"], fake_enrolled("1003", 60) + 1)
        self.assertTrue(c["enrolledSimulated"])

    def test_credit_max(self):
        self.add("1008")
        r = self.submit()
        self.assertEqual(r.status_code, 409)
        self.assertIn("學分超過", r.json()["reason"])

    def test_credit_min(self):
        self.add("1014", "drop")
        self.add("1015", "drop")
        r = self.submit()
        self.assertEqual(r.status_code, 409)
        self.assertIn("學分不足", r.json()["reason"])

    def test_full_course_simulated_seats(self):
        self.add(FULL)
        r = self.submit()
        self.assertEqual(r.status_code, 409)
        self.assertIn("額滿", r.json()["reason"])
        self.assertIn("模擬", r.json()["reason"])

    def test_restriction(self):
        self.add("1006")
        r = self.submit()
        self.assertEqual(r.status_code, 409)
        self.assertIn("限修不符", r.json()["reason"])
        self.assertIn("你是 3 年級", r.json()["reason"])

    def test_placeholder_and_duplicates_rejected(self):
        self.assertEqual(self.add("BDC99713@資科三B").status_code, 400)
        self.assertEqual(self.add("1001").status_code, 409)          # 已在課表上
        self.assertEqual(self.add("1003", "drop").status_code, 409)  # 不在課表上不能退
        self.assertEqual(self.add("NOPE").status_code, 404)

    def test_empty_cart_submit(self):
        self.assertEqual(self.submit().status_code, 400)

    def test_drop_and_add_same_submit(self):
        self.add("1001", "drop")
        self.add("1002")                                              # 退 1001 後 1002 就不衝堂了
        r = self.submit()
        self.assertEqual(r.status_code, 200, r.content.decode())
        self.assertIn("1002", self.tt())
        self.assertNotIn("1001", self.tt())

    @override_settings(SCU_DEMO_AUTOLOGIN=False)
    def test_login_required_when_autologin_off(self):
        self.assertEqual(self.client.get("/api/cart").status_code, 401)
        self.client.login(username="demo", password="demo1234")
        self.assertEqual(self.client.get("/api/cart").status_code, 200)


class EligibilityUnitTests(TestCase):
    student = {"program": "學士班", "dept": "資料科學系", "grade": 3, "classLabel": "資科三B"}

    def test_dept_abbreviation(self):
        self.assertTrue(dept_match("資科系", "資料科學系"))
        self.assertTrue(dept_match("中文系", "中國文學系"))
        self.assertFalse(dept_match("英文系", "資料科學系"))

    def test_rules(self):
        self.assertTrue(can_take(None, self.student)["ok"])
        self.assertFalse(can_take({"g": [1, 2]}, self.student)["ok"])
        self.assertTrue(can_take({"min": 3}, self.student)["ok"])
        self.assertFalse(can_take({"d": ["英文系"]}, self.student)["ok"])
        self.assertFalse(can_take({"dn": ["資料科學系"]}, self.student)["ok"])
        self.assertTrue(can_take({"dn": ["英文系"]}, self.student)["ok"])
        self.assertFalse(can_take({"c": ["資科三A"]}, self.student)["ok"])
        self.assertFalse(can_take({"x": "限重補修生"}, self.student)["ok"])
