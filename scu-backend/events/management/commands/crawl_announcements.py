"""python manage.py crawl_announcements [--pages 2]

只更新「校園公告」（news.scu.edu.tw + 德育中心最新消息）。建議每天 2 次（見 README 排程）。
其實就是 crawl_events --only news 的捷徑：示範 call_command() 如何在指令裡呼叫另一個指令。
"""
from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "抓校園公告（news.scu.edu.tw 前幾頁，≥1.5 秒/請求，遇 403/429 立即停止）"

    def add_arguments(self, p):
        p.add_argument("--pages", type=int, default=2, help="公告列表抓幾頁（每頁 20 筆）")
        p.add_argument("--detail-limit", type=int, default=5, help="最多進幾篇內頁找發布單位")

    def handle(self, pages, detail_limit, **_):
        call_command("crawl_events", only="news", news_pages=pages, news_detail_limit=detail_limit,
                     stdout=self.stdout, stderr=self.stderr)
