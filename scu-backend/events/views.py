"""events/views.py — GET /api/events、GET /api/news、GET /api/bundle/events"""
from django.views.decorators.http import require_GET

from config.api import api_ok, int_or_none

from .services import front_events, front_meta, front_news


@require_GET
def events_api(request):
    evs, _, _ = front_events(year=int_or_none(request.GET.get("year")) or 115,
                             include_staff=request.GET.get("audience") == "all")
    t = request.GET.get("type")
    if t:
        evs = [e for e in evs if e["type"] == t]
    return api_ok(evs)


@require_GET
def news_api(request):
    n = min(int_or_none(request.GET.get("limit")) or 60, 300)
    return api_ok(front_news(n))


@require_GET
def events_bundle(request):
    """= real-events.js 的三個全域變數：SCU_REAL_META / SCU_REAL_EVENTS / SCU_REAL_NEWS"""
    evs, cal_src, since = front_events()
    news = front_news(60)
    return api_ok({"meta": front_meta(evs, news, cal_src, since), "events": evs, "news": news})
