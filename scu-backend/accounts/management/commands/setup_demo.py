"""python manage.py setup_demo [--reset]

建立示範帳號 demo / demo1234（王小明，學士班 資料科學系 三年級 B 班），
並依「資科三B」班級課表產生初始課表（必修＋幾門選修，約 18 學分）。
要先跑 import_timetable_db，才找得到班級。--reset 會清掉 demo 的課表與選課車重新產生。
"""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from accounts.models import StudentProfile
from accounts.services import student_of
from enrollment.services import seed_timetable

DEMO = dict(name="王小明", student_id="11316025", program="學士班", dept="資料科學系", college="巨量資料管理學院",
            grade=3, cls="B", campus="城中校區")


class Command(BaseCommand):
    help = "建立示範學生帳號與初始課表"

    def add_arguments(self, p):
        p.add_argument("--reset", action="store_true")
        p.add_argument("--password", default="demo1234")

    def handle(self, reset, password, **_):
        User = get_user_model()
        user, created = User.objects.get_or_create(username=settings.SCU_DEMO_USERNAME,
                                                   defaults={"first_name": "小明", "last_name": "王"})
        if created or reset:
            user.set_password(password)
            user.save()
        StudentProfile.objects.update_or_create(user=user, defaults=DEMO)
        user.refresh_from_db()
        student, my_class = student_of(user)
        codes = seed_timetable(user, student, my_class, reset=reset)
        self.stdout.write(self.style.SUCCESS(
            f"示範帳號 {user.username}（{'新建' if created else '已存在'}）；班級：{student['classLabel'] or '找不到（請先匯入課程）'}；"
            f"課表 {len(codes)} 門：{', '.join(codes)}"))
