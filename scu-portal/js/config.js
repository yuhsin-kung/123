/* =========================================================================
 * config.js — 示範設定（整個網站唯一需要改「今天是哪天」的地方）
 * -------------------------------------------------------------------------
 * DEMO_NOW：示範用的「今天」日期與時間。首頁「今天的課」「全校事務快到了」、
 *           課表的「今天」欄、行事曆的倒數天數都以這個時間計算，
 *           所以不論哪天打開網站，畫面都一樣好展示。
 * 也可以用網址參數臨時覆寫（不用改程式）：
 *   index.html?date=2026-10-05&time=09:00      → 看星期一早上
 *   index.html?date=2026-10-03                  → 星期六（沒有課；未給 time 時沿用 DEMO_NOW.time）
 *   index.html?date=2026-10-09                  → 國慶日補假（放假，沒有課）
 * ========================================================================= */
var SCU = window.SCU = window.SCU || {};

/* 預設跟這台電腦的系統時間。網址 ?date=&time= 仍可暫時覆寫。 */

/* 阿斯拉語言模型（trade-rag，本機 7861）。關鍵字先查站內，再請它改寫。 */
SCU.ASLA_API = 'http://127.0.0.1:7861/api/chat';

/* 示範登入學生的資料放在 js/profile.js */

/* 目前學期（示範） */
SCU.SEMESTER = { code: '115-1', label: '115 學年度第 1 學期', start: '2026-09-14', end: '2027-01-15' };

/* ---- 解析網址參數 ?date=YYYY-MM-DD&time=HH:MM ---- */
(function () {
  var q = new URLSearchParams(location.search);
  var d = q.get('date'), t = q.get('time');
  var now = new Date();
  var pad = function (n) { return String(n).padStart(2, '0'); };
  var date = now.getFullYear() + '-' + pad(now.getMonth() + 1) + '-' + pad(now.getDate());
  var time = pad(now.getHours()) + ':' + pad(now.getMinutes());
  var fromUrl = false;
  if (d && /^\d{4}-\d{2}-\d{2}$/.test(d) && !isNaN(new Date(d + 'T00:00:00').getTime())) { date = d; fromUrl = true; }
  if (t && /^([01]\d|2[0-3]):[0-5]\d$/.test(t)) { time = t; fromUrl = true; }
  SCU.DEMO_NOW = { date: date, time: time };
  SCU.NOW = { date: date, time: time, fromUrl: fromUrl };
})();
