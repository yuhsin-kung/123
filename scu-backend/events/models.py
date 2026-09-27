"""events/models.py — 全校事務：行事曆事件、校園公告、爬蟲紀錄

從 scu-events/django_draft/events/models.py 複製，加中文 verbose_name；
first_seen 改成 default=timezone.now（匯入舊資料時能保留原本的首次看到時間）。
選課時段（初選、加退選…）也是 Event（category="選課"），enrollment app 從這裡推算「現在能不能選課」。
"""
from django.db import models
from django.utils import timezone


class Event(models.Model):
    class Category(models.TextChoices):
        COURSE = "選課", "選課"
        FEE = "繳費", "繳費"
        EXAM = "考試", "考試"
        HOLIDAY = "放假", "放假"
        SCHOLARSHIP = "獎助學金", "獎助學金"
        SCHOOL = "學校", "學校"
        NOTICE = "公告", "公告"

    # 前端 SCU.EVENT_TYPES 的 key
    FRONT_TYPE = {"選課": "course", "繳費": "fee", "考試": "exam", "放假": "holiday",
                  "獎助學金": "school", "學校": "school", "公告": "school"}

    source_name = models.CharField("來源", max_length=40, db_index=True)  # scu_calendar_ics / scu_course_timetable / ...
    uid = models.CharField("來源內唯一鍵", max_length=200)
    title = models.CharField("標題", max_length=300)
    category = models.CharField("分類", max_length=8, choices=Category.choices, db_index=True)
    start_date = models.DateField("開始日", db_index=True)
    end_date = models.DateField("結束日（含）", null=True, blank=True)
    source_url = models.URLField("來源網址", max_length=500, blank=True)
    raw_text = models.TextField("原始文字", blank=True)   # 選課時間表的「時間」欄在這裡，例如 "17 日 | 9:00 24:00 | 初選…"
    hash = models.CharField(max_length=40, db_index=True)
    semester = models.CharField("學期", max_length=8, blank=True, db_index=True)
    audience = models.CharField("對象", max_length=10, default="student")   # student / staff
    note = models.TextField("備註", blank=True)
    is_active = models.BooleanField("有效", default=True)
    fetched_at = models.DateTimeField("抓取時間")
    first_seen = models.DateTimeField("首次看到", default=timezone.now)
    updated_at = models.DateTimeField("更新時間", auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["source_name", "uid"], name="uniq_event_source_uid")]
        ordering = ["start_date", "end_date"]
        verbose_name = verbose_name_plural = "行事曆事件"

    def __str__(self):
        return f"{self.start_date} {self.title}"

    def to_front(self):
        d = {"id": f"scu-{self.pk}", "start": self.start_date.isoformat(),
             "type": self.FRONT_TYPE.get(self.category, "school"), "title": self.title,
             "desc": self.note or "", "route": "#/calendar", "category": self.category,
             "semester": self.semester, "sourceUrl": self.source_url}
        if self.end_date and self.end_date != self.start_date:
            d["end"] = self.end_date.isoformat()
        return d


class Announcement(models.Model):
    source_name = models.CharField("來源", max_length=40, default="news")
    news_id = models.CharField("公告編號", max_length=40)
    title = models.CharField("標題", max_length=500)
    date = models.DateField("登刊日期", null=True, blank=True, db_index=True)
    unit = models.CharField("發布單位", max_length=60, blank=True)
    category = models.CharField("網站分類", max_length=20, blank=True)
    tag = models.CharField("關鍵字分類", max_length=8, blank=True)
    url = models.URLField("網址", max_length=500, blank=True)
    hash = models.CharField(max_length=40)
    fetched_at = models.DateTimeField("抓取時間")
    first_seen = models.DateTimeField("首次看到", default=timezone.now)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["source_name", "news_id"], name="uniq_ann_source_id")]
        ordering = ["-date", "-id"]
        verbose_name = verbose_name_plural = "校園公告"

    def __str__(self):
        return f"{self.date} {self.title[:40]}"

    def to_front(self):
        """與前端 SCU_REAL_NEWS 相同欄位"""
        return {"date": self.date.isoformat() if self.date else "", "unit": self.unit or "", "title": self.title,
                "tag": self.tag or "公告", "category": self.category, "url": self.url, "source": self.source_name}


class CrawlLog(models.Model):
    source_name = models.CharField("來源", max_length=40)
    started_at = models.DateTimeField("開始")
    finished_at = models.DateTimeField("結束", auto_now_add=True)
    status = models.CharField("狀態", max_length=10)   # ok / error / blocked
    n_items = models.IntegerField("筆數", default=0)
    message = models.TextField("訊息", blank=True)

    class Meta:
        ordering = ["-started_at"]
        verbose_name = verbose_name_plural = "行事曆／公告爬蟲紀錄"

    def __str__(self):
        return f"{self.started_at:%Y-%m-%d %H:%M} {self.source_name} {self.status}"
