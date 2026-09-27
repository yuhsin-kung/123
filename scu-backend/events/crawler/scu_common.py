"""Shared helpers: polite HTTP session, date helpers, categorisation.

Used by scrape_events.py (standalone, SQLite) and can be imported by the
Django management command draft (django_draft/).
"""
from __future__ import annotations

import hashlib
import os
import re
import time
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests

TZ = ZoneInfo("Asia/Taipei")
UA = ("SCU-Portal-Demo-EventsBot/0.1 (student portal demo; public pages only; "
      "polite >=1.2s delay; contact: project maintainer)")
MIN_INTERVAL = 1.5  # seconds between requests (requirement: >= 1.2s)

HERE = os.path.dirname(os.path.abspath(__file__))
CA_BUNDLE = os.path.join(HERE, "certs", "ca_bundle.pem")
SECTIGO_OV_URL = "http://crt.sectigo.com/SectigoRSAOrganizationValidationSecureServerCA.crt"
# www.scu.edu.tw does not send its intermediate certificate; we add the public
# Sectigo intermediate to certifi's bundle so TLS is still fully verified.
HOSTS_NEEDING_BUNDLE = {"www.scu.edu.tw"}


class Blocked(Exception):
    """Raised on HTTP 403/429: the crawler must stop immediately."""


class PoliteSession:
    def __init__(self, min_interval: float = MIN_INTERVAL, timeout: int = 30, log=print):
        if min_interval < 1.2:
            raise ValueError("min_interval must be >= 1.2s")
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": UA, "Accept-Language": "zh-TW,zh;q=0.9"})
        self.min_interval = min_interval
        self.timeout = timeout
        self._last = 0.0
        self.log = log
        self.n_requests = 0

    def _wait(self):
        dt = time.monotonic() - self._last
        if dt < self.min_interval:
            time.sleep(self.min_interval - dt)
        self._last = time.monotonic()

    def get(self, url: str, **kw) -> requests.Response:
        from urllib.parse import urlparse
        host = urlparse(url).hostname or ""
        if host in HOSTS_NEEDING_BUNDLE:
            kw.setdefault("verify", ensure_ca_bundle(self))
        self._wait()
        self.n_requests += 1
        r = self.s.get(url, timeout=self.timeout, **kw)
        self.log(f"  GET {r.status_code} {url}")
        if r.status_code in (403, 429):
            raise Blocked(f"HTTP {r.status_code} from {url} - stopping crawl")
        r.raise_for_status()
        return r


def ensure_ca_bundle(sess: "PoliteSession | None" = None) -> str:
    """Build certs/ca_bundle.pem = certifi roots + Sectigo OV intermediate (once)."""
    if os.path.exists(CA_BUNDLE):
        return CA_BUNDLE
    import ssl
    import certifi
    os.makedirs(os.path.dirname(CA_BUNDLE), exist_ok=True)
    der = requests.get(SECTIGO_OV_URL, headers={"User-Agent": UA}, timeout=30).content
    pem = ssl.DER_cert_to_PEM_cert(der)
    with open(certifi.where(), "r", encoding="ascii") as f, open(CA_BUNDLE, "w", encoding="ascii") as out:
        out.write(f.read() + "\n" + pem)
    return CA_BUNDLE


def now_iso() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def sha1(*parts) -> str:
    return hashlib.sha1("|".join("" if p is None else str(p) for p in parts).encode("utf-8")).hexdigest()


def roc_to_ad(y: int) -> int:
    return y + 1911 if y < 1000 else y


def academic_year_window(roc_year: int) -> tuple[date, date]:
    """115 -> 2026-08-01 .. 2027-07-31"""
    y = roc_to_ad(roc_year)
    return date(y, 8, 1), date(y + 1, 7, 31)


def semester_of(d: date) -> str:
    """Return e.g. '115-1' / '115-2' for a date (Aug-Jan = 1st, Feb-Jul = 2nd)."""
    if d.month >= 8:
        return f"{d.year - 1911}-1"
    if d.month == 1:
        return f"{d.year - 1912}-1"
    return f"{d.year - 1912}-2"


# ---------------------------------------------------------------------------
# Title cleaning / categorisation
# ---------------------------------------------------------------------------
# "1日~9月6日暑假。" / "15~24日連續休假10天。" / "30 日~12 月 11 日課程期末退修申請。"
PREFIX_RE = re.compile(
    r"^\s*(?P<d1>\d{1,2})\s*(?:日)?\s*(?:[~～]\s*(?:(?P<m2>\d{1,2})\s*月\s*)?(?P<d2>\d{1,2})\s*)?日\s*")


def clean_title(summary: str):
    """Strip the leading day prefix used in SCU's calendar; returns
    (clean_title, prefix_start_day, prefix_end_month, prefix_end_day)."""
    s = re.sub(r"\s+", " ", summary).strip()
    m = PREFIX_RE.match(s)
    d1 = m2 = d2 = None
    if m:
        d1 = int(m.group("d1"))
        m2 = int(m.group("m2")) if m.group("m2") else None
        d2 = int(m.group("d2")) if m.group("d2") else None
        s = s[m.end():]
    s = s.strip().rstrip("。").strip()
    # compact spaces between CJK chars introduced by PDF extraction
    s = re.sub(r"(?<=[\u4e00-\u9fff\d]) (?=[\u4e00-\u9fff])", "", s)
    s = re.sub(r"(?<=[\u4e00-\u9fff]) (?=\d)", "", s)
    return s, d1, m2, d2


CATEGORY_RULES = [
    ("學校", re.compile(r"開學日|上課開始|學期開始|學期結束")),
    ("考試", re.compile(r"考試|期中考|期末考|補考|英檢|多益")),
    ("放假", re.compile(r"放假|補假|假期|寒假|暑假|連續休假|兒童節|掃墓節|停課")),
    ("選課", re.compile(r"選課|加退選|加選|退選|退修|雙主修|輔系|跨領域學程|轉系|逕行修讀|第二專長|選課清單")),
    ("繳費", re.compile(r"繳費|學雜|退還|減免|就學貸款|就貸|繳費單")),
    ("獎助學金", re.compile(r"獎學金|助學金|獎助學金|餐券補助|工讀|急難救助|紓困")),
]
STAFF_RE = re.compile(r"會議|教師|授課計畫|成績提交")


def categorize(title: str, default: str = "學校") -> str:
    if "補班" in title and "放假" not in title:
        return "學校"
    for cat, rx in CATEGORY_RULES:
        if cat == "獎助學金" and "教師" in title:
            continue
        if rx.search(title):
            return cat
    return default


def audience_of(title: str) -> str:
    if categorize(title) == "放假":
        return "student"
    return "staff" if STAFF_RE.search(title) else "student"
