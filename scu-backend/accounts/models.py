"""accounts/models.py — 學生個人資料（示範：王小明）

Django 內建的 User 只有帳號、密碼、姓名、email。學制／系所／年級這些學校才有的欄位，
用「一對一 (OneToOneField)」另外開一張 StudentProfile 表掛在 User 上 → 這是擴充 User 最常見的做法。
"""
from django.conf import settings
from django.db import models


class StudentProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile",
                                verbose_name="帳號")
    name = models.CharField("姓名", max_length=40)
    student_id = models.CharField("學號", max_length=12, unique=True)
    program = models.CharField("學制", max_length=20, default="學士班")
    dept = models.CharField("系所", max_length=40)
    college = models.CharField("學院", max_length=40, blank=True)   # 選課時段有「巨量學院各系」這種限定
    grade = models.PositiveSmallIntegerField("年級")
    cls = models.CharField("班別", max_length=4, blank=True)         # 'B'
    campus = models.CharField("校區", max_length=20, blank=True)
    is_demo = models.BooleanField("示範帳號", default=True)

    class Meta:
        verbose_name = verbose_name_plural = "學生資料"

    def __str__(self):
        return f"{self.student_id} {self.name}"

    def to_front(self, class_label=""):
        """與前端 js/profile.js 的 SCU.PROFILE 相同欄位（再多幾個欄位，前端會忽略）"""
        return {"name": self.name, "studentId": self.student_id, "program": self.program, "dept": self.dept,
                "grade": self.grade, "cls": self.cls, "campus": self.campus, "college": self.college,
                "classLabel": class_label, "username": self.user.username, "demo": self.is_demo}
