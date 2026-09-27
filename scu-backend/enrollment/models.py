"""enrollment/models.py — 選課：我的課表、選課車、送出紀錄、示範時鐘

設計重點（寫報告可提）：
  * 課程用 course_key（= Course.offering_key，通常是「選課編號」）存字串，而不是 ForeignKey。
    因為每學期重新匯入課程時 Course 會整批刪掉重建，用 ForeignKey 會把大家的選課一起刪掉（CASCADE）。
  * 已選人數：學校沒有公開，所以是「模擬」的（timetable.catalog.fake_enrolled ＋ 本系統送出的加選數）。
"""
from django.conf import settings
from django.db import models


class Enrollment(models.Model):
    """已選上的課（= 前端「我的課表」）"""
    class Source(models.TextChoices):
        SEED = "seed", "示範初始課表"
        SUBMIT = "submit", "送出選課"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="enrollments",
                             verbose_name="學生帳號")
    semester = models.CharField("學期", max_length=6, db_index=True)
    course_key = models.CharField("課程鍵（選課編號）", max_length=60)
    source = models.CharField("來源", max_length=8, choices=Source.choices, default=Source.SUBMIT)
    created_at = models.DateTimeField("建立時間", auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "semester", "course_key"], name="uniq_enrollment")]
        ordering = ["id"]
        verbose_name = verbose_name_plural = "我的課表（已選上）"

    def __str__(self):
        return f"{self.user} {self.semester} {self.course_key}"


class CartItem(models.Model):
    """選課車：待加選 add／待退選 drop（送出前可以隨時修改）"""
    class Action(models.TextChoices):
        ADD = "add", "加選"
        DROP = "drop", "退選"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="cart_items",
                             verbose_name="學生帳號")
    semester = models.CharField("學期", max_length=6, db_index=True)
    course_key = models.CharField("課程鍵（選課編號）", max_length=60)
    action = models.CharField("動作", max_length=4, choices=Action.choices)
    created_at = models.DateTimeField("加入時間", auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "semester", "course_key"], name="uniq_cart_item")]
        ordering = ["id"]
        verbose_name = verbose_name_plural = "選課車"

    def __str__(self):
        return f"{self.user} {self.action} {self.course_key}"


class Submission(models.Model):
    """每次按「送出」的紀錄（成功或被擋都記），方便在 admin 看發生什麼事"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="學生帳號")
    semester = models.CharField("學期", max_length=6)
    demo_now = models.DateTimeField("示範時間")
    created_at = models.DateTimeField("實際時間", auto_now_add=True)
    ok = models.BooleanField("成功")
    status_code = models.PositiveSmallIntegerField("HTTP 狀態碼")
    added = models.JSONField("加選", default=list)
    dropped = models.JSONField("退選", default=list)
    reasons = models.JSONField("原因", default=list)

    class Meta:
        ordering = ["-id"]
        verbose_name = verbose_name_plural = "送出紀錄"


class DemoClock(models.Model):
    """示範時鐘（只會有一筆）：在 admin 打勾「啟用」並填時間，就能改變系統認為的「現在」。
    沒有啟用時用 settings.SCU_DEMO_NOW（預設 2026-09-30 10:30）。"""
    enabled = models.BooleanField("啟用", default=False)
    now = models.DateTimeField("示範的現在時間")
    note = models.CharField("說明", max_length=100, blank=True)

    class Meta:
        verbose_name = verbose_name_plural = "示範時鐘"

    def __str__(self):
        return f"{'啟用' if self.enabled else '停用'} {self.now}"
