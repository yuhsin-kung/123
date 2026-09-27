"""timetable/models.py — 課程資料的資料表（Model = 一張資料表，一個屬性 = 一個欄位）

從 scu-scraper/django_draft/timetable/models.py 複製過來，再加上：
  * 中文 verbose_name（admin 介面顯示中文）
  * extra JSONField：爬蟲 SQLite 之後若多了新欄位（例如第二專長標記），匯入時先放這裡，不會遺失

所有資料都用 semester（"115-1" = 115 學年第 1 學期）分開。一學期爬一次（crawl_timetable）
或從爬蟲的 SQLite 匯入（import_timetable_db），都會「整個學期換新」。

關聯圖：
  Program(學制) 1─* Department(系所) 1─* SchoolClass(班級) *─* Course(課程)   ← 透過 ClassCourse(必/選)
  Course 1─* CourseSession(上課時段)        CourseRestriction(限修條件) 以 (semester, course_code) 對應 Course
"""
from django.db import models

# 前端節次順序（1–4、E、5–9、A–D）＝學校課表的 1..14 格
PERIOD_ORDER = "1234E56789ABCD"
PERIOD_TIMES = [("1", "08:10", "09:00"), ("2", "09:10", "10:00"), ("3", "10:10", "11:00"), ("4", "11:10", "12:00"),
                ("E", "12:10", "13:00"), ("5", "13:10", "14:00"), ("6", "14:10", "15:00"), ("7", "15:10", "16:00"),
                ("8", "16:10", "17:00"), ("9", "17:10", "18:00"), ("A", "18:25", "19:15"), ("B", "19:20", "20:10"),
                ("C", "20:20", "21:10"), ("D", "21:15", "22:05")]
# 「通識類」系所（班級課表上屬於這些類別的課，前端標成「通識」）
GENERAL_DEPTS = {"通識", "生命關懷", "思維方法", "數位自學", "職涯錨定", "ＡＩ跨域", "AI跨域", "全校選修"}


class ScrapeRun(models.Model):
    class Status(models.TextChoices):
        RUNNING = "running", "執行中"
        OK = "ok", "成功"
        FAILED = "failed", "失敗"

    semester = models.CharField("學期", max_length=6, db_index=True)
    started_at = models.DateTimeField("開始時間")
    finished_at = models.DateTimeField("結束時間", null=True, blank=True)
    status = models.CharField("狀態", max_length=10, choices=Status.choices, default=Status.RUNNING)
    is_full = models.BooleanField("全校完整抓取", default=False)
    n_classes = models.PositiveIntegerField("班級數", default=0)
    n_requests = models.PositiveIntegerField("HTTP 請求數", default=0)
    raw_dir = models.CharField("原始 HTML 資料夾", max_length=500, blank=True)
    note = models.TextField("備註", blank=True)

    class Meta:
        ordering = ["-started_at"]
        verbose_name = verbose_name_plural = "爬蟲執行紀錄"

    def __str__(self):
        from django.utils import timezone
        return f"{self.semester} {timezone.localtime(self.started_at):%Y-%m-%d %H:%M} {self.status}"


class ScrapedModel(models.Model):
    """抽象類別（abstract）：共用欄位，不會自己產生資料表 → 教「繼承」的好例子"""
    semester = models.CharField("學期", max_length=6, db_index=True)
    scrape_run = models.ForeignKey(ScrapeRun, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    scraped_at = models.DateTimeField("抓取時間")

    class Meta:
        abstract = True


class Program(ScrapedModel):                      # 部別: 學士班/碩士班/...
    code = models.CharField("代碼", max_length=2)            # '1'
    form_value = models.CharField("表單值", max_length=40)   # '1學士班'  (POST clsid1)
    label = models.CharField("學制", max_length=40)          # '學士班'

    class Meta:
        constraints = [models.UniqueConstraint(fields=["semester", "code"], name="uniq_program")]
        ordering = ["semester", "code"]
        verbose_name = verbose_name_plural = "學制"

    def __str__(self):
        return f"{self.semester} {self.label}"


class Department(ScrapedModel):                   # 學系或科目類別
    program = models.ForeignKey(Program, on_delete=models.CASCADE, related_name="departments", verbose_name="學制")
    form_value = models.CharField("表單值", max_length=60)   # '7373資料科學系' (POST clsid02)
    label = models.CharField("系所／類別", max_length=60)     # '資料科學系'
    class_key = models.CharField(max_length=6)               # '173' (JS class1[] index; debugging only)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["semester", "program", "form_value"], name="uniq_dept")]
        ordering = ["id"]
        verbose_name = verbose_name_plural = "系所"

    @property
    def is_general(self):
        return self.label in GENERAL_DEPTS

    def __str__(self):
        return f"{self.program.label} {self.label}"


class SchoolClass(ScrapedModel):                  # 班級 ('Class' avoided: reserved-ish in Python)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name="classes", verbose_name="系所")
    form_value = models.CharField("表單值", max_length=40)   # '717332資科三Ｂ　' (keep trailing U+3000!)
    label = models.CharField("班級", max_length=30)          # '資科三B' (NFKC-normalized)
    abbr = models.CharField("簡稱", max_length=20, blank=True)            # '資科'
    grade = models.PositiveSmallIntegerField("年級", null=True, blank=True)  # 3
    section = models.CharField("班別", max_length=2, blank=True)          # 'B'
    timetable_scraped_at = models.DateTimeField("課表抓取時間", null=True, blank=True)
    courses = models.ManyToManyField("Course", through="ClassCourse", related_name="classes")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["semester", "department", "form_value"], name="uniq_class")]
        indexes = [models.Index(fields=["semester", "label"])]
        ordering = ["id"]
        verbose_name = verbose_name_plural = "班級"

    def __str__(self):
        return self.label


class Course(ScrapedModel):
    course_code = models.CharField("科目代碼", max_length=12, db_index=True)   # BDD30102
    selection_no = models.CharField("選課編號", max_length=8, blank=True)      # 4264 ('' = 時段保留列)
    offering_key = models.CharField("課程鍵", max_length=60)                   # 前端的 code：選課編號 或 科目代碼@班級
    name = models.CharField("課名", max_length=200)
    offering_class = models.CharField("開課班級", max_length=30, blank=True)
    group_name = models.CharField("組別", max_length=60, blank=True)           # e.g. 遠距教學
    term_type = models.CharField("全/單", max_length=2, blank=True)
    credits = models.DecimalField("學分", max_digits=4, decimal_places=1, null=True, blank=True)
    hours = models.DecimalField("時數", max_digits=4, decimal_places=1, null=True, blank=True)
    capacity = models.PositiveIntegerField("人數上限", null=True, blank=True)
    teacher = models.CharField("教師", max_length=100, blank=True)
    note = models.CharField("備註", max_length=200, blank=True)
    plan_url = models.URLField("授課計畫", max_length=500, blank=True)
    teacher_url = models.URLField(max_length=500, blank=True)
    extra = models.JSONField("其他欄位", default=dict, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["semester", "course_code", "offering_key"], name="uniq_course")]
        indexes = [models.Index(fields=["semester", "offering_key"])]
        ordering = ["course_code", "selection_no"]
        verbose_name = verbose_name_plural = "課程"

    @property
    def is_placeholder(self):
        """班級課表上沒有選課編號的列（通識時段、系會時間）：不能選、不計學分、不算衝堂"""
        return not self.selection_no

    def __str__(self):
        return f"{self.selection_no or '-'} {self.name}"


class ClassCourse(models.Model):                   # course listed on a class timetable
    school_class = models.ForeignKey(SchoolClass, on_delete=models.CASCADE, verbose_name="班級")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, verbose_name="課程")
    req_elective = models.CharField("必/選", max_length=2, blank=True)   # can differ per class

    class Meta:
        constraints = [models.UniqueConstraint(fields=["school_class", "course"], name="uniq_class_course")]
        verbose_name = verbose_name_plural = "班級課表列"


class CourseSession(models.Model):
    class Weekday(models.IntegerChoices):
        MON = 1, "一"
        TUE = 2, "二"
        WED = 3, "三"
        THU = 4, "四"
        FRI = 5, "五"
        SAT = 6, "六"
        SUN = 7, "日"

    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="sessions", verbose_name="課程")
    weekday = models.PositiveSmallIntegerField("星期", choices=Weekday.choices, null=True, blank=True)
    periods = models.CharField("節次", max_length=16, blank=True)   # '34E', '789', 'AB'
    start_time = models.TimeField("開始", null=True, blank=True)
    end_time = models.TimeField("結束", null=True, blank=True)
    week_type = models.CharField("單雙週", max_length=2, blank=True)  # ''/單/雙/前/後
    room = models.CharField("教室", max_length=20, blank=True)
    teacher = models.CharField("教師", max_length=100, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["course", "weekday", "periods", "room", "week_type"],
                                               name="uniq_session")]
        verbose_name = verbose_name_plural = "上課時段"

    def slot_runs(self):
        """'34E' → [(3, 5)]：轉成前端用的連續節次區間（1..14）"""
        idx = sorted({PERIOD_ORDER.index(ch) + 1 for ch in (self.periods or "") if ch in PERIOD_ORDER})
        runs = []
        for i in idx:
            if runs and i == runs[-1][1] + 1:
                runs[-1][1] = i
            else:
                runs.append([i, i])
        unknown = any(ch not in PERIOD_ORDER for ch in (self.periods or "").strip())
        return [tuple(r) for r in runs], unknown

    def __str__(self):
        return f"{self.get_weekday_display() or '?'} {self.periods} {self.room}"


class CourseRule(models.Model):
    """學校公開「選課限制資料查詢」(SelectCar/selrule12.asp) 的原始一列"""
    semester = models.CharField("學期", max_length=6, db_index=True)
    course_code = models.CharField("科目代碼", max_length=12, db_index=True)
    rule_code = models.CharField(max_length=4, blank=True)
    description = models.CharField("說明", max_length=60, blank=True)      # '限修-開學後'
    phase = models.CharField("階段", max_length=4, blank=True)             # 開學前 / 開學後
    allow = models.BooleanField("可選", null=True)                        # 可選 / 不可選
    dimension = models.CharField("條件類型", max_length=20, blank=True)    # 年級 / 部別 / 學系 / 班級 …
    values = models.JSONField("條件值", default=list)
    exceptions = models.JSONField("例外", default=list)
    raw = models.TextField(blank=True)
    scraped_at = models.DateTimeField()

    class Meta:
        verbose_name = verbose_name_plural = "選課限制（原始列）"


class CourseRestriction(models.Model):
    """每個 (學期, 科目代碼) 整理後的限修條件（來自 CourseRule + 備註推測）"""
    class Source(models.TextChoices):
        SELRULE = "selrule"
        NOTE = "note"
        BOTH = "selrule+note"
        NONE = "none"

    semester = models.CharField("學期", max_length=6)
    course_code = models.CharField("科目代碼", max_length=12, db_index=True)
    min_grade = models.PositiveSmallIntegerField("最低年級", null=True, blank=True)
    max_grade = models.PositiveSmallIntegerField("最高年級", null=True, blank=True)
    grades = models.JSONField("限年級", null=True, blank=True)        # [2,3]
    dept_only = models.JSONField("限系所", null=True, blank=True)     # ["資料科學系"]
    program_only = models.JSONField("限學制", null=True, blank=True)  # ["學士班"]
    class_only = models.JSONField("限班級", null=True, blank=True)
    dept_exclude = models.JSONField("不可選學系", null=True, blank=True)  # ["英文系"]
    exceptions = models.JSONField("例外身分", null=True, blank=True)
    other_text = models.TextField("其他", blank=True)
    source = models.CharField("來源", max_length=14, choices=Source.choices, default=Source.NONE)
    rules_checked = models.BooleanField("已查學校限修資料", default=False)
    scraped_at = models.DateTimeField()
    extra = models.JSONField("其他欄位", default=dict, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["semester", "course_code"], name="uniq_restriction")]
        verbose_name = verbose_name_plural = "限修條件"

    def to_front(self):
        """前端 real-courses.js 的 restr 物件（縮寫欄位：g/min/d/p/c/dn/e/x/src/chk）"""
        o = {}
        if self.grades:
            o["g"] = self.grades
        elif self.min_grade:
            o["min"] = self.min_grade
        if self.dept_only:
            o["d"] = self.dept_only
        if self.program_only:
            o["p"] = self.program_only
        if self.class_only:
            o["c"] = self.class_only
        if self.dept_exclude:
            o["dn"] = self.dept_exclude
        if self.exceptions:
            o["e"] = self.exceptions
        if self.other_text:
            o["x"] = self.other_text
        o["src"] = self.source
        o["chk"] = 1 if self.rules_checked else 0
        return o

    def __str__(self):
        return f"{self.semester} {self.course_code}"
