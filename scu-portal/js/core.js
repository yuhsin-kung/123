/* =========================================================================
 * core.js — 共用核心（所有頁面都會用到）
 * -------------------------------------------------------------------------
 *  1. 小工具：$、esc（HTML 跳脫）、toast、SVG 圖示
 *  2. 日期時間：以 config.js 的示範「今天」為準（S.today、S.nowMin、fmtDate…）
 *  3. 使用者資料狀態：課表 timetable、選課車 cart、名額異動 seatDelta、期中退選 withdrawn
 *     （讀寫一律經過 js/data-source.js，現為 localStorage，之後可換成後端 API）
 *  4. 課程工具：剩餘名額、衝堂判斷、學分計算、某天的課（classesOn）
 *  5. 送出前檢查 runChecks：衝堂／學分 16–25／額滿，並找替代課程
 *  6. 週課表格線 timetableGrid（課表頁、選課預覽共用）
 *  7. 行事曆工具：放假判斷、倒數天數
 *  8. 路由 router：#/home、#/timetable、#/course、#/grades、#/calendar、#/more、#/p/功能、#/settings
 *  9. 全站點擊事件分派（data-act）
 * 頁面本身寫在 js/pages/*.js，透過 S.views 註冊。
 * ========================================================================= */
(function () {
  'use strict';
  const S = window.SCU;

  /* ---------- 1. 小工具 ---------- */
  const $ = (sel, root) => (root || document).querySelector(sel);
  const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  S.$ = $; S.$$ = $$; S.esc = esc;

  S.toast = function (msg) {
    const t = $('#toast'); t.textContent = msg; t.hidden = false;
    clearTimeout(S.toast._t); S.toast._t = setTimeout(() => { t.hidden = true; }, 2400);
  };

  const ICONS = {
    home: 'M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z',
    table: 'M5 4h14a2 2 0 0 1 2 2v13a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2zM3 9h18M9 4v17M15 4v17',
    course: 'M4 19.5A2.5 2.5 0 0 1 6.5 17H20V3H6.5A2.5 2.5 0 0 0 4 5.5v14zM4 19.5A2.5 2.5 0 0 0 6.5 22H20v-5M12 7v6M9 10h6',
    chart: 'M4 20V11M10 20V5M16 20v-6M21 20H3',
    more: 'M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h6v6h-6z',
    calendar: 'M5 5h14a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2zM3 10h18M8 3v4M16 3v4',
    clock: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM12 7v5l3 2',
    pin: 'M12 21s-7-6.2-7-11.5A7 7 0 0 1 19 9.5C19 14.8 12 21 12 21zM12 7.5a2 2 0 1 0 0 4 2 2 0 0 0 0-4z',
    user: 'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4 21a8 8 0 0 1 16 0',
    chat: 'M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z',
    search: 'M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14zM21 21l-5-5',
    right: 'M9 6l6 6-6 6', left: 'M15 6l-6 6 6 6',
    x: 'M6 6l12 12M18 6 6 18', check: 'M5 12.5l4.5 4.5L19 7',
    alert: 'M12 3 2 20h20L12 3zM12 10v4M12 17.5v.01',
    cart: 'M3 4h2l2.4 11.2a1 1 0 0 0 1 .8h9.2a1 1 0 0 0 1-.8L20 8H6.2M9 20.5a.5.5 0 1 0 0-1 .5.5 0 0 0 0 1zM17 20.5a.5.5 0 1 0 0-1 .5.5 0 0 0 0 1z',
    plus: 'M12 5v14M5 12h14', minus: 'M5 12h14', back: 'M19 12H5M11 6l-6 6 6 6',
    undo: 'M9 14 4 9l5-5M4 9h10.5a5.5 5.5 0 0 1 0 11H11',
    out: 'M12 16V4M8 8l4-4 4 4M4 20h16',
    target: 'M12 12m-8 0a8 8 0 1 0 16 0a8 8 0 1 0-16 0M12 12m-4 0a4 4 0 1 0 8 0a4 4 0 1 0-8 0M12 12m-1 0a1 1 0 1 0 2 0a1 1 0 1 0-2 0',
    sun: 'M12 7a5 5 0 1 0 0 10 5 5 0 0 0 0-10zM12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4',
    cap: 'M3 9.5 12 5l9 4.5L12 14 3 9.5zM7 12v4.5c0 1 2.2 2.5 5 2.5s5-1.5 5-2.5V12',
    hands: 'M8 13v-2a2 2 0 1 1 4 0M12 11V8a2 2 0 1 1 4 0v5M8 13l-2 5h12l-1.5-4',
    file: 'M7 3h7l5 5v13a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1zM14 3v6h6',
    horn: 'M4 10v4a2 2 0 0 0 2 2h2l6 4V4L8 8H6a2 2 0 0 0-2 2zM18 9a4 4 0 0 1 0 6',
    mail: 'M4 6h16v12H4zM4 7l8 6 8-6',
    pay: 'M3 7h18v10H3zM3 11h18M7 15h4',
    bank: 'M4 10h16M6 10v8M10 10v8M14 10v8M18 10v8M3 18h18M12 4l9 6H3z',
    park: 'M4 18V8h6l2 3h8v7M7 18a2 2 0 1 0 0 .01M17 18a2 2 0 1 0 0 .01',
    medal: 'M9 4h6l-1 5a4 4 0 1 1-4 0L9 4zM8 20l4-3 4 3',
    life: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 8v5M12 16v.01',
    thermo: 'M10 14.5V6a2 2 0 1 1 4 0v8.5a4 4 0 1 1-4 0zM12 6v6',
    book: 'M5 4h6a3 3 0 0 1 3 3v13a3 3 0 0 0-3-3H5zM19 4h-6a3 3 0 0 0-3 3v13a3 3 0 0 1 3-3h6z',
    id: 'M4 6h16v12H4zM8 10h3M8 14h5M16 12a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3z',
    building: 'M4 20V6l8-3 8 3v14M9 20v-5h6v5M9 9h.01M12 9h.01M15 9h.01M9 12h.01M12 12h.01M15 12h.01',
    mic: 'M12 3a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3zM6 11a6 6 0 0 0 12 0M12 17v4',
    masks: 'M4 8a4 4 0 0 1 8 0v3H4zM12 8a4 4 0 0 1 8 0v3h-8zM7 10h.01M17 10h.01',
    bag: 'M8 8V6a4 4 0 0 1 8 0v2M5 8h14l-1 12H6z',
    board: 'M4 5h16v10H4zM8 19h8M12 15v4',
    compass: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM14.5 9.5 13 13l-3.5 1.5L11 11z',
    heart: 'M12 20s-7-4.4-7-9a4 4 0 0 1 7-2 4 4 0 0 1 7 2c0 4.6-7 9-7 9z',
    shield: 'M12 3 5 6v6c0 4.2 3 6.8 7 8 4-1.2 7-3.8 7-8V6z',
    gear: 'M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7zM12 3v2M12 19v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M3 12h2M19 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4'
  };
  S.icon = (name, cls) => `<svg class="ic ${cls || ''}" viewBox="0 0 24 24" aria-hidden="true"><path d="${ICONS[name] || ''}"/></svg>`;

  /* ---------- 2. 日期時間（示範「今天」） ---------- */
  const WD = ['日', '一', '二', '三', '四', '五', '六'];
  S.WD = WD;
  S.parseDate = (s) => { const [y, m, d] = s.split('-').map(Number); return new Date(y, m - 1, d); };
  S.ymd = (dt) => `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, '0')}-${String(dt.getDate()).padStart(2, '0')}`;
  S.addDays = (s, n) => { const d = S.parseDate(s); d.setDate(d.getDate() + n); return S.ymd(d); };
  S.daysBetween = (a, b) => Math.round((S.parseDate(b) - S.parseDate(a)) / 86400000); /* b - a */
  S.weekday = (s) => S.parseDate(s).getDay(); /* 0=日 … 6=六 */
  S.fmtDate = (s, withWd) => { const d = S.parseDate(s); return `${d.getMonth() + 1}/${d.getDate()}${withWd === false ? '' : `（${WD[d.getDay()]}）`}`; };
  S.toMin = (hhmm) => { const [h, m] = hhmm.split(':').map(Number); return h * 60 + m; };
  S.today = S.NOW.date;
  S.nowMin = S.toMin(S.NOW.time);
  S.semesterWeek = function (date) {
    const d = S.daysBetween(S.SEMESTER.start, date || S.today);
    if (d < 0 || date > S.SEMESTER.end) return 0;
    return Math.floor(d / 7) + 1;
  };
  S.periodStart = (p) => DS.getPeriods()[p - 1].t.split('–')[0];
  S.periodEnd = (p) => DS.getPeriods()[p - 1].t.split('–')[1];

  /* ---------- 3. 使用者資料狀態（透過 data-source.js 讀寫，現為 localStorage） ---------- */
  const DS = S.DS;
  const state = S.state = { timetable: [], cart: { add: [], drop: [] }, seatDelta: {}, withdrawn: [] };
  S.initState = function () { /* main.js 在 DS.init() 之後呼叫 */
    state.timetable = DS.getMyTimetable();   /* 已選上的課（課程代碼） */
    state.cart = DS.getCart();               /* 選課車：待加選 add、待退選 drop */
    state.seatDelta = DS.getSeatDelta();     /* 送出後名額變化（示範） */
    state.withdrawn = DS.getWithdrawn();     /* 期中退選（W）的課 */
  };
  S.save = function () {
    DS.saveMyTimetable(state.timetable); DS.saveCart(state.cart); DS.saveSeatDelta(state.seatDelta); DS.saveWithdrawn(state.withdrawn);
  };
  S.resetDemo = function () { DS.resetMyData(); S.initState(); };

  /* ---------- 4. 課程工具 ---------- */
  S.remain = (c) => Math.max(0, c.cap - c.enrolled - (state.seatDelta[c.code] || 0));
  S.coursesOf = (codes) => codes.map(DS.getCourse).filter(Boolean);
  S.myCourses = () => {
    const P = DS.getProfile();
    if (P && P.role === 'teacher') {
      return DS.getCourses().filter((c) => (c.teacher || '').indexOf(P.name) >= 0);
    }
    return S.coursesOf(state.timetable);
  };
  S.sumCredits = (list) => list.reduce((a, c) => a + c.credits, 0);
  S.inTimetable = (code) => state.timetable.indexOf(code) >= 0;
  S.inCartAdd = (code) => state.cart.add.indexOf(code) >= 0;
  S.inCartDrop = (code) => state.cart.drop.indexOf(code) >= 0;
  S.cartCount = () => state.cart.add.length + state.cart.drop.length;
  /* 送出後的課表 = 目前課表 − 待退選 + 待加選 */
  S.plannedCodes = () => state.timetable.filter((c) => !S.inCartDrop(c)).concat(state.cart.add.filter((c) => !S.inTimetable(c)));
  S.plannedCourses = () => S.coursesOf(S.plannedCodes());

  S.overlap = function (a, b) {
    const out = [];
    a.slots.forEach((x) => b.slots.forEach((y) => {
      if (x.day === y.day && x.start <= y.end && y.start <= x.end) out.push({ day: x.day, from: Math.max(x.start, y.start), to: Math.min(x.end, y.end) });
    }));
    return out;
  };
  S.conflictsWith = (course, list) => list.filter((o) => o.code !== course.code && S.overlap(course, o).length);
  S.remainBadge = function (c) {
    const r = S.remain(c);
    if (r <= 0) return `<span class="seat seat-full">額滿 0/${c.cap}</span>`;
    if (r < 5) return `<span class="seat seat-low">剩 ${r}/${c.cap}</span>`;
    return `<span class="seat seat-ok">剩 ${r}/${c.cap}</span>`;
  };
  S.typeTag = (c) => `<span class="type type-${c.type}">${c.type}</span>`;
  S.slotRange = (s) => `${S.periodStart(s.start)}–${S.periodEnd(s.end)}`;

  /* 某一天的課（依示範課表），回傳依開始時間排序的清單 */
  S.classesOn = function (date, codes) {
    const wd = S.weekday(date); const out = [];
    S.coursesOf(codes || state.timetable).forEach((c) => c.slots.forEach((s) => {
      if (s.day === wd) out.push({ c, s, startT: S.periodStart(s.start), endT: S.periodEnd(s.end), startMin: S.toMin(S.periodStart(s.start)), endMin: S.toMin(S.periodEnd(s.end)) });
    }));
    return out.sort((a, b) => a.startMin - b.startMin);
  };

  /* ---------- 5. 送出前檢查 ---------- */
  function findConflicts(list) {
    const out = [];
    for (let i = 0; i < list.length; i++) for (let j = i + 1; j < list.length; j++) {
      const ov = S.overlap(list[i], list[j]);
      if (ov.length) out.push({ a: list[i], b: list[j], ov });
    }
    return out;
  }
  S.findConflicts = findConflicts;
  S.alternativesFor = function (bad, planned, limit) {
    const rest = planned.filter((c) => c.code !== bad.code);
    const used = new Set(planned.map((c) => c.code));
    const score = (c) => (c.dept === bad.dept ? 0 : 10) + (c.type === bad.type ? 0 : 3) + Math.abs(c.credits - bad.credits);
    return DS.getCourses().filter((c) => !used.has(c.code) && S.remain(c) > 0 && !S.conflictsWith(c, rest).length)
      .sort((a, b) => score(a) - score(b) || S.remain(b) - S.remain(a)).slice(0, limit || 3);
  };
  S.fillSuggestions = function (planned, limit) {
    const used = new Set(planned.map((c) => c.code));
    const rank = (c) => (c.dept === DS.getProfile().dept ? 0 : c.type === '通識' ? 1 : 2);
    return DS.getCourses().filter((c) => !used.has(c.code) && S.remain(c) > 0 && !S.conflictsWith(c, planned).length)
      .sort((a, b) => rank(a) - rank(b) || S.remain(b) - S.remain(a)).slice(0, limit || 4);
  };
  /* 回傳 { planned, credits, conflicts, full, creditIssue, ok, conflictCodes } */
  S.runChecks = function () {
    const planned = S.plannedCourses();
    const credits = S.sumCredits(planned);
    const conflicts = findConflicts(planned);
    const full = planned.filter((c) => S.inCartAdd(c.code) && !S.inTimetable(c.code) && S.remain(c) <= 0);
    const r = DS.getCreditRule();
    const creditIssue = credits < r.min ? 'low' : credits > r.max ? 'high' : '';
    const conflictCodes = new Set(); conflicts.forEach((x) => { conflictCodes.add(x.a.code); conflictCodes.add(x.b.code); });
    return { planned, credits, conflicts, full, creditIssue, conflictCodes, ok: !conflicts.length && !full.length && !creditIssue };
  };

  /* ---------- 6. 週課表格線 ---------- */
  /* opts: { conflictCodes:Set, newCodes:Set, todayDay:1-5, compact:bool } */
  S.timetableGrid = function (list, opts) {
    opts = opts || {};
    const PER = DS.getPeriods(); const P = PER.length;
    let g = `<div class="tt-h tt-corner" style="grid-column:1;grid-row:1">節</div>`;
    for (let d = 1; d <= 5; d++) g += `<div class="tt-h ${opts.todayDay === d ? 'is-today' : ''}" style="grid-column:${d + 1};grid-row:1">${WD[d]}${opts.todayDay === d ? '<small>今天</small>' : ''}</div>`;
    PER.forEach((p) => {
      g += `<div class="tt-p" style="grid-column:1;grid-row:${p.p + 1}"><b>${p.label || p.p}</b><small>${(p.t || '').split('–')[0]}</small></div>`;
      for (let d = 1; d <= 5; d++) g += `<div class="tt-cell ${opts.todayDay === d ? 'is-today' : ''}" style="grid-column:${d + 1};grid-row:${p.p + 1}"></div>`;
    });
    const blocks = [];
    list.forEach((c) => c.slots.forEach((s) => blocks.push({ c, s })));
    for (let d = 1; d <= 5; d++) { /* 衝堂時左右並排 */
      const day = blocks.filter((b) => b.s.day === d).sort((a, b) => a.s.start - b.s.start);
      day.forEach((b, i) => {
        b.half = day.some((o) => o !== b && o.s.start <= b.s.end && b.s.start <= o.s.end);
        /* 取「前面重疊區塊沒用到」的最小欄位（0 左、1 右） */
        const used = day.filter((o, j) => j < i && o.s.start <= b.s.end && b.s.start <= o.s.end).map((o) => o.lane);
        b.lane = b.half ? (used.indexOf(0) < 0 ? 0 : 1) : 0;
      });
    }
    blocks.forEach((b) => {
      const c = b.c; const r = S.remain(c);
      const cls = ['tt-blk', 'c' + (DS.getCourses().indexOf(c) % 6), opts.conflictCodes && opts.conflictCodes.has(c.code) ? 'is-conflict' : '',
        opts.newCodes && opts.newCodes.has(c.code) ? 'is-new' : '', b.half ? 'half' : '', b.lane ? 'lane1' : ''].join(' ');
      g += `<div class="${cls}" style="grid-column:${b.s.day + 1};grid-row:${b.s.start + 1} / ${b.s.end + 2}" title="${esc(c.name)}｜${esc(c.teacher)}｜${esc(c.room)}｜${S.slotRange(b.s)}">
        <b>${esc(c.name)}</b><span class="tt-room">${esc(c.room)}</span>
        <span class="tt-seat ${r <= 0 ? 'full' : r < 5 ? 'low' : ''}">${r > 0 ? '剩 ' + r + ' 位' : '額滿'}</span>
        ${opts.conflictCodes && opts.conflictCodes.has(c.code) ? '<span class="tt-flag">衝堂</span>' : opts.newCodes && opts.newCodes.has(c.code) ? '<span class="tt-flag new">新加選</span>' : ''}</div>`;
    });
    return `<div class="tt-scroll"><div class="tt" style="grid-template-rows:auto repeat(${P}, minmax(46px, auto))">${g}</div></div>`;
  };

  /* 一節一格的課表（星期一到五，E 節排在第 4 節與第 5 節之間） */
  S.timetableSheet = function (list) {
    const order = DS.getPeriods().slice().sort((a, b) => {
      const rank = (p) => {
        const lab = String(p.label || p.p);
        if (lab === 'E') return 4.5;
        if (/^\d+$/.test(lab)) return +lab;
        return 20 + lab.charCodeAt(0);
      };
      return rank(a) - rank(b);
    });
    const used = new Set();
    list.forEach((c) => (c.slots || []).forEach((s) => { for (let p = s.start; p <= s.end; p++) used.add(p); }));
    const rows = order.filter((p) => {
      const lab = String(p.label || p.p);
      if (lab === 'E' || (/^\d+$/.test(lab) && +lab >= 1 && +lab <= 9)) return true;
      return used.has(p.p);
    });
    const names = ['', '星期一', '星期二', '星期三', '星期四', '星期五'];
    const rowPs = rows.map((p) => p.p);
    const at = (day, p) => {
      const hits = [];
      list.forEach((c) => (c.slots || []).forEach((s) => {
        if (s.day === day && s.start <= p && s.end >= p) hits.push({ c, s });
      }));
      const seen = new Set();
      return hits.filter((h) => {
        const k = h.c.code + '|' + (h.s.room || '') + '|' + (h.s.week || '');
        if (seen.has(k)) return false;
        seen.add(k);
        return true;
      });
    };
    const tone = (code) => {
      let n = 0;
      String(code || '').split('').forEach((ch) => { n = (n + ch.charCodeAt(0)) % 6; });
      return n;
    };
    const cellHtml = (hits) => hits.map((h) => {
      const room = h.s.room || h.c.room || '';
      const week = h.s.week === '單' || h.s.week === '雙' ? h.s.week + '週' : '';
      const meta = [room, week, h.c.teacher].filter(Boolean).join(' · ');
      return `<div class="blk c${tone(h.c.code)}"><b>${esc(h.c.name)}</b>${meta ? `<small>${esc(meta)}</small>` : ''}</div>`;
    }).join('');
    const days = [1, 2, 3, 4, 5].map(() => []);
    for (let d = 0; d < 5; d++) {
      const col = days[d];
      for (let i = 0; i < rowPs.length; i++) {
        if (col[i]) continue;
        const hits = at(d + 1, rowPs[i]);
        if (!hits.length) { col[i] = { empty: true }; continue; }
        let span = 1;
        const only = hits.length === 1 ? hits[0] : null;
        if (only) {
          while (i + span < rowPs.length) {
            const next = at(d + 1, rowPs[i + span]);
            if (next.length !== 1 || next[0].c.code !== only.c.code || next[0].s.room !== only.s.room || next[0].s.week !== only.s.week) break;
            if (rowPs[i + span] < only.s.start || rowPs[i + span] > only.s.end) break;
            span++;
          }
        }
        col[i] = { hits, span };
        for (let k = 1; k < span; k++) col[i + k] = { skip: true };
      }
    }
    let body = '';
    rows.forEach((p, i) => {
      const noon = String(p.label || p.p) === 'E' ? ' noon' : '';
      body += `<tr class="${noon.trim()}"><th class="pn">${esc(p.label || p.p)}</th>`;
      days.forEach((col) => {
        const cell = col[i];
        if (!cell || cell.skip) return;
        if (cell.empty) body += '<td></td>';
        else body += `<td rowspan="${cell.span}">${cellHtml(cell.hits)}</td>`;
      });
      body += '</tr>';
    });
    const head = `<tr><th class="pn">節次</th>${[1, 2, 3, 4, 5].map((d) => `<th class="wd${d}">${names[d]}</th>`).join('')}</tr>`;
    return `<div class="tt-scroll"><table class="sheet">${head}${body}</table></div>`;
  };

  /* 手機：一次只看一天，不要橫向滑整張表 */
  S.dayClassesHtml = function (list, day) {
    const per = DS.getPeriods();
    const hits = [];
    (list || []).forEach((c) => (c.slots || []).forEach((s) => { if (s.day === day) hits.push({ c, s }); }));
    hits.sort((a, b) => a.s.start - b.s.start || a.c.name.localeCompare(b.c.name, 'zh-Hant'));
    if (!hits.length) return '<p class="empty">這天沒有課</p>';
    return `<div class="m-classes">${hits.map((h) => {
      const a = per[h.s.start - 1]; const b = per[h.s.end - 1];
      const lab = a && b ? (a.label === b.label ? a.label : `${a.label}–${b.label}`) : '';
      const meta = [h.s.room, h.s.week ? h.s.week + '週' : '', h.c.teacher].filter(Boolean).join(' · ');
      return `<article class="m-class"><span class="m-per">${esc(lab)}</span><div><b>${esc(h.c.name)}</b><small>${esc(meta)}</small></div></article>`;
    }).join('')}</div>`;
  };
  S.mobileWeek = function (list) {
    const names = ['', '一', '二', '三', '四', '五'];
    const today = S.weekday(S.today);
    const day = today >= 1 && today <= 5 ? today : 1;
    const btns = [1, 2, 3, 4, 5].map((d) => `<button type="button" class="m-day ${d === day ? 'on' : ''}" data-mday="${d}">${names[d]}</button>`).join('');
    return `<div class="m-board only-phone"><div class="m-days" role="tablist">${btns}</div><div class="m-body">${S.dayClassesHtml(list, day)}</div></div>`;
  };

  /* ---------- 7. 行事曆工具 ---------- */
  S.eventEnd = (e) => e.end || e.start;
  S.holidayOn = (date) => DS.getEvents().find((e) => e.type === 'holiday' && e.start <= date && S.eventEnd(e) >= date) || null;
  S.eventsOn = (date) => DS.getEvents().filter((e) => e.start <= date && S.eventEnd(e) >= date);
  /* 倒數：{ n, label, state:'ongoing'|'upcoming'|'past', urgent } */
  S.countdown = function (e, today) {
    today = today || S.today;
    const end = S.eventEnd(e);
    if (end < today) return { state: 'past', n: 0, big: '已結束', label: '已結束' };
    if (e.start <= today) {
      const n = S.daysBetween(today, end);
      if (e.start === end) return { state: 'ongoing', n: 0, big: '今天', label: '就是今天', urgent: true };
      return { state: 'ongoing', n, big: n === 0 ? '今天' : n, unit: n === 0 ? '截止' : '天後截止', label: n === 0 ? '進行中・今天截止' : `進行中・剩 ${n} 天截止`, urgent: n <= 3 };
    }
    const n = S.daysBetween(today, e.start);
    return { state: 'upcoming', n, big: n === 1 ? '明天' : n, unit: n === 1 ? '' : '天後', label: n === 1 ? '明天開始' : `還有 ${n} 天`, urgent: n <= 3 };
  };
  S.upcomingEvents = function (limit, days) {
    return DS.getEvents().filter((e) => S.eventEnd(e) >= S.today && S.daysBetween(S.today, e.start) <= (days || 120))
      .sort((a, b) => {
        /* 進行中的排前面，其次依開始日 */
        const oa = a.start <= S.today ? 0 : 1, ob = b.start <= S.today ? 0 : 1;
        return oa - ob || a.start.localeCompare(b.start);
      }).slice(0, limit || 6);
  };
  S.eventRange = (e) => (e.end && e.end !== e.start ? `${S.fmtDate(e.start)} – ${S.fmtDate(e.end)}` : S.fmtDate(e.start));
  S.evTag = (e) => `<span class="ev-tag ${DS.getEventTypes()[e.type].cls}">${DS.getEventTypes()[e.type].name}</span>`;

  /* ---------- 8. 路由 ---------- */
  S.views = {};    /* 各頁面：S.views.home = { tab, title, render(params) → HTML, after(params) } */
  S.actions = {};  /* 各頁面註冊的按鈕動作：S.actions['cart-add'] = (el, event) => {} */
  S.parseHash = function () {
    const h = location.hash.replace(/^#\/?/, '');
    const [path, qs] = h.split('?');
    const parts = (path || 'home').split('/');
    return { route: parts[0] || 'home', sub: parts[1] || '', params: new URLSearchParams(qs || '') };
  };
  S.go = function (hash) { if (location.hash === hash) S.render(); else location.hash = hash; };
  S.render = function (keepScroll) {
    const { route, sub, params } = S.parseHash();
    const r = S.views[route] ? route : 'home';
    const v = S.views[r];
    $('#view').innerHTML = v.render(params, sub);
    const tab = typeof v.tab === 'function' ? v.tab(sub) : v.tab;
    $$('[data-tab]').forEach((a) => { const on = a.dataset.tab === tab || (a.dataset.also || '').split(' ').indexOf(tab) >= 0; a.classList.toggle('active', on); if (on) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current'); });
    const feat = DS.featureForHash && DS.featureForHash(location.hash);
    if (feat && S._usedHash !== location.hash) { S._usedHash = location.hash; DS.bumpUse(feat.id); }
    document.title = (typeof v.title === 'function' ? v.title(sub) : v.title) + '｜東吳學生新入口';
    S.updateBadges();
    if (v.after) v.after(params, sub);
    if (!keepScroll && !params.get('focus')) window.scrollTo(0, 0);
  };
  S.refresh = () => S.render(true);
  S.updateBadges = function () {
    const n = S.cartCount();
    $$('.cart-badge').forEach((b) => { b.textContent = n; b.hidden = !n; });
  };
  window.addEventListener('hashchange', () => S.render());

  /* ---------- 9. 全站點擊事件分派 ---------- */
  document.addEventListener('click', (e) => {
    const t = e.target.closest('[data-act]'); if (!t) return;
    const fn = S.actions[t.dataset.act];
    if (fn) { e.preventDefault(); fn(t, e); }
  });
  S.actions.nav = (t) => S.go(t.dataset.href);
  document.addEventListener('click', (e) => {
    const b = e.target.closest('[data-mday]'); if (!b) return;
    const board = b.closest('.m-board'); if (!board) return;
    const day = +b.dataset.mday;
    board.querySelectorAll('[data-mday]').forEach((x) => x.classList.toggle('on', x === b));
    const body = board.querySelector('.m-body');
    if (body) body.innerHTML = S.dayClassesHtml(S.myCourses(), day);
  });
  S.actions['open-asla'] = (t) => S.openAsla && S.openAsla(t.dataset.q);
  S.actions['demo-badge'] = () => S.toast('示範資料：本網站為黑客松原型，課程、成績、日期皆為虛構，不連接學校系統。');
})();
