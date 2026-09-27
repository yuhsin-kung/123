"""timetable/services.py — 依學生身分找班級（不連網）。原本 draft 的 class_for_profile，改用 catalog 快取。"""
from django.conf import settings

from .catalog import get_catalog


def class_for_profile(program, dept, grade, section, semester=None):
    return get_catalog(semester or settings.SCU_SEMESTER).find_class(program, dept, grade, section)
