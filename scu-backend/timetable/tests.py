"""timetable/tests.py — 課程 API 與前端相容格式（bundle）的測試"""
from enrollment.tests import EnrollmentTestBase


class TimetableApiTests(EnrollmentTestBase):
    def test_courses_filter_by_dept_grade(self):
        r = self.client.get("/api/courses?dept=資料科學系&grade=3").json()
        codes = {c["code"] for c in r["results"]}
        self.assertIn("1001", codes)
        self.assertNotIn("1007", codes)                   # 通識不在資料科學系班級課表
        self.assertNotIn("BDC99713@資科三B", codes)       # 時段保留列不出現在找課結果

    def test_courses_filter_by_day_period_and_eligible(self):
        r = self.client.get("/api/courses?day=4&period=6-7").json()
        self.assertEqual({c["code"] for c in r["results"]}, {"1003", "1004"})
        r = self.client.get("/api/courses?day=4&period=1&eligible=1").json()
        self.assertEqual(r["count"], 0)                   # 1006 限一年級，被濾掉

    def test_course_detail_shape(self):
        c = self.client.get("/api/courses/1001").json()
        for k in ("code", "no", "cid", "name", "teacher", "credits", "cap", "slots", "restr", "enrolled",
                  "enrolledSimulated", "listings", "type", "eligible"):
            self.assertIn(k, c)
        self.assertEqual(c["slots"][0], {"day": 2, "start": 7, "end": 8, "room": "H101", "wk": "", "teacher": ""})  # 節次 6、7 = 第 7、8 格（E 佔第 5 格）
        self.assertEqual(c["type"], "必修")

    def test_class_timetable(self):
        r = self.client.get("/api/class-timetable?program=學士班&dept=資料科學系&grade=3&cls=B").json()
        self.assertEqual(r["cls"]["label"], "資科三B")
        self.assertEqual(r["reqs"]["1001"], "必")
        i = r["cls"]["i"]
        self.assertEqual(self.client.get(f"/api/classes/{i}/timetable").json()["codes"], r["codes"])
        self.assertEqual(self.client.get("/api/classes/999999/timetable").status_code, 404)

    def test_bundles_have_frontend_shape(self):
        b = self.client.get("/api/bundle/courses").json()
        self.assertEqual(set(b), {"meta", "periods", "fields", "courses"})
        self.assertEqual(len(b["courses"][0]), 16)
        k = self.client.get("/api/bundle/classes").json()
        self.assertEqual(set(k), {"fields", "programs", "depts", "classes"})
        self.assertEqual(k["programs"], [["1", "學士班"]])

    def test_profile(self):
        p = self.client.get("/api/profile").json()
        self.assertEqual((p["name"], p["dept"], p["grade"], p["cls"], p["classLabel"]),
                         ("王小明", "資料科學系", 3, "B", "資科三B"))
        self.assertIn("csrftoken", self.client.cookies)
