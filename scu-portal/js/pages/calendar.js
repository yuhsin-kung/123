/* =========================================================================
 * pages/calendar.js — 行事曆（#/calendar）
 * -------------------------------------------------------------------------
 * 資料來源與首頁「全校事務快到了」相同（data-source.js 的 getEvents()）。
 * 列表模式 (?view=list)：依月份分組，已過去的變淡，並在今天的位置插入「今天」分隔線。
 * 月曆模式 (?view=month&m=YYYY-MM)：月曆格子，放假日紅字，點日期看當天事項。
 * 類別篩選 (?type=course|fee|exam|holiday|school)。
 * ========================================================================= */
(function () {
  'use strict';
  const S = window.SCU; const esc = S.esc; const DS = S.DS;

  function link(p, patch) {
    const q = new URLSearchParams(p.toString()); Object.keys(patch).forEach((k) => (patch[k] == null ? q.delete(k) : q.set(k, patch[k])));
    return '#/calendar?' + q.toString();
  }
  function evRow(e) {
    const cd = S.countdown(e);
    return `<a class="cal-row ${cd.state === 'past' ? 'is-past' : ''} ${cd.urgent ? 'is-urgent' : ''}" href="${esc(e.route || '#/calendar')}">
      <div class="cal-date"><b>${S.parseDate(e.start).getDate()}</b><small>週${S.WD[S.weekday(e.start)]}</small></div>
      <div class="cal-body"><div class="ev-line">${S.evTag(e)}<span class="small muted">${S.eventRange(e)}</span></div>
        <h3>${esc(e.title)}</h3><p class="small muted">${esc(e.desc || '')}</p></div>
      <div class="cal-cd">${cd.state === 'past' ? '已結束' : esc(cd.label)}</div></a>`;
  }
  function listView(evs) {
    let html = '', month = '', todayDone = false;
    evs.forEach((e) => {
      const m = e.start.slice(0, 7);
      if (!todayDone && S.eventEnd(e) >= S.today) {
        html += `<div class="today-line" id="today-line"><span>今天 ${S.fmtDate(S.today)}</span></div>`; todayDone = true;
      }
      if (m !== month) { month = m; html += `<h3 class="cal-month">${m.slice(0, 4)} 年 ${+m.slice(5)} 月</h3>`; }
      html += evRow(e);
    });
    if (!todayDone) html += `<div class="today-line" id="today-line"><span>今天 ${S.fmtDate(S.today)}</span></div>`;
    return `<div class="card flush cal-list">${html || '<div class="empty">沒有符合的事項。</div>'}</div>`;
  }
  function monthView(evs, ym, p) {
    const [y, m] = ym.split('-').map(Number);
    const first = new Date(y, m - 1, 1); const days = new Date(y, m, 0).getDate();
    const prev = S.ymd(new Date(y, m - 2, 1)).slice(0, 7), next = S.ymd(new Date(y, m, 1)).slice(0, 7);
    let cells = ['日', '一', '二', '三', '四', '五', '六'].map((d) => `<div class="mc-h">${d}</div>`).join('');
    for (let i = 0; i < first.getDay(); i++) cells += '<div class="mc mc-empty"></div>';
    for (let d = 1; d <= days; d++) {
      const ds = `${ym}-${String(d).padStart(2, '0')}`;
      const on = evs.filter((e) => e.start <= ds && S.eventEnd(e) >= ds);
      const hol = on.some((e) => e.type === 'holiday'); const wd = S.weekday(ds);
      cells += `<div class="mc ${ds === S.today ? 'is-today' : ''} ${hol || wd === 0 || wd === 6 ? 'is-off' : ''}"><span class="mc-d">${d}</span>
        ${on.slice(0, 2).map((e) => `<span class="mc-ev ${DS.getEventTypes()[e.type].cls}" title="${esc(e.title)}">${esc(e.title)}</span>`).join('')}${on.length > 2 ? `<span class="mc-more">+${on.length - 2}</span>` : ''}</div>`;
    }
    const inMonth = evs.filter((e) => e.start.slice(0, 7) <= ym && S.eventEnd(e).slice(0, 7) >= ym);
    return `<div class="card month">
      <div class="month-nav"><a class="icon-btn" href="${link(p, { m: prev })}" aria-label="上個月">${S.icon('left')}</a><b>${y} 年 ${m} 月</b><a class="icon-btn" href="${link(p, { m: next })}" aria-label="下個月">${S.icon('right')}</a></div>
      <div class="mgrid">${cells}</div></div>
      <div class="card flush cal-list section">${inMonth.length ? inMonth.map(evRow).join('') : '<div class="empty">這個月沒有事項。</div>'}</div>`;
  }

  S.views.calendar = {
    tab: 'calendar', title: '行事曆',
    render(p) {
      const view = p.get('view') === 'month' ? 'month' : 'list';
      const type = DS.getEventTypes()[p.get('type')] ? p.get('type') : '';
      const evs = DS.getEvents().filter((e) => !type || e.type === type);
      const ym = /^\d{4}-\d{2}$/.test(p.get('m') || '') ? p.get('m') : S.today.slice(0, 7);
      const T = DS.getEventTypes();
      return `<div class="page-head"><div><h1>行事曆</h1><p class="muted small">${S.SEMESTER.label}（示範日期）</p></div>
        <div class="seg small"><a href="${link(p, { view: null })}" class="${view === 'list' ? 'on' : ''}">列表</a><a href="${link(p, { view: 'month' })}" class="${view === 'month' ? 'on' : ''}">月曆</a></div></div>
        <div class="chips filter-chips"><a class="chip ${!type ? 'on' : ''}" href="${link(p, { type: null })}">全部</a>${Object.keys(T).map((k) => `<a class="chip ${type === k ? 'on' : ''}" href="${link(p, { type: k })}"><i class="dot ${T[k].cls}"></i>${T[k].name}</a>`).join('')}</div>
        ${view === 'month' ? monthView(evs, ym, p) : listView(evs)}`;
    }
  };
})();
