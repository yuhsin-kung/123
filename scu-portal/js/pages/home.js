/* =========================================================================
 * pages/home.js — 首頁（#/home）
 * -------------------------------------------------------------------------
 * 版面（示意圖）：左側功能選單、上方打字搜尋、中間常用功能（可改看全部）、
 *   左下阿斯拉、中下今天的課、右側課表與行事曆。
 * ========================================================================= */
(function () {
  'use strict';
  const S = window.SCU; const esc = S.esc; const DS = S.DS;

  function greet(min) { return min < 11 * 60 ? '早安' : min < 14 * 60 ? '午安' : min < 18 * 60 ? '午後好' : '晚安'; }
  function inSemester(d) { return d >= S.SEMESTER.start && d <= S.SEMESTER.end; }
  function dayClasses(d) { return (!S.holidayOn(d) && inSemester(d)) ? S.classesOn(d) : []; }

  /* 往後找下一個有課的日子（最多 21 天） */
  function nextClassDay(from) {
    for (let i = 1; i <= 21; i++) { const d = S.addDays(from, i); const cl = dayClasses(d); if (cl.length) return { d, first: cl[0], n: cl.length }; }
    return null;
  }

  function todayStrip() {
    const d = S.today; const wd = S.weekday(d); const hol = S.holidayOn(d);
    const list = dayClasses(d); const now = S.nowMin;
    if (!list.length) {
      const why = hol ? `今天是「${esc(hol.title)}」，沒有課` : (wd === 0 || wd === 6) ? '今天是週末，沒有課' : !inSemester(d) ? '目前不在上課期間' : '今天沒有排課';
      const nx = nextClassDay(d);
      return `<a class="today-strip is-empty" href="#/timetable"><b>${why}</b><span>${nx ? `下一堂 ${S.fmtDate(nx.d)} ${nx.first.startT} ${esc(nx.first.c.name)}` : '看課表'}</span></a>`;
    }
    let nextFound = false;
    const pills = list.map((x) => {
      let st = 'later';
      if (x.endMin <= now) st = 'done';
      else if (x.startMin <= now) st = 'now';
      else if (!nextFound) { st = 'next'; nextFound = true; }
      const label = st === 'now' ? '上課中' : st === 'next' ? '下一堂' : st === 'done' ? '已結束' : '今天';
      return `<a class="today-pill is-${st}" href="#/timetable"><small>${x.startT} ${label}</small><b>${esc(x.c.name)}</b><span>${esc(x.c.room)}</span></a>`;
    }).join('');
    return `<section class="today-strip" aria-label="今天的課"><span class="today-kicker">${S.icon('clock')}今天 ${list.length} 堂</span><div class="today-pills">${pills}</div></section>`;
  }

  function eventsSection() {
    const evs = S.upcomingEvents(8);
    const rows = evs.map((e) => {
      const cd = S.countdown(e);
      return `<a class="ev-row ${cd.urgent ? 'is-urgent' : ''} ${cd.state === 'ongoing' ? 'is-ongoing' : ''}" href="${esc(e.route || '#/calendar')}">
        <div class="ev-count ${S.DS.getEventTypes()[e.type].cls}"><b>${cd.big}</b><small>${cd.unit || ''}</small></div>
        <div class="ev-body"><div class="ev-line">${S.evTag(e)}${cd.state === 'ongoing' ? '<span class="ev-on">進行中</span>' : ''}</div>
          <h3>${esc(e.title)}</h3><p>${S.eventRange(e)}</p></div>${S.icon('right', 'chev')}</a>`;
    }).join('');
    return `<section class="card sec-events" aria-labelledby="h-ev">
      <div class="sec-head"><h2 id="h-ev">${S.icon('calendar')}行事曆</h2><a class="link-more" href="#/calendar">看全部 ${S.icon('right')}</a></div>
      ${rows ? `<div class="ev-list">${rows}</div>` : '<div class="empty">最近沒有全校事務。</div>'}</section>`;
  }

  const COMMON_SEED = ['course', 'timetable', 'grades', 'calendar', 'fee', 'dorm', 'scholarship', 'news'];
  function commonItems(items) {
    const counts = DS.useCounts();
    const ranked = items.filter((it) => counts[it.id]).sort((a, b) => counts[b.id] - counts[a.id] || a.name.localeCompare(b.name, 'zh-Hant'));
    const ids = ranked.slice(0, 8).map((it) => it.id);
    if (!ids.length) return COMMON_SEED.map((id) => items.find((it) => it.id === id)).filter(Boolean);
    COMMON_SEED.forEach((id) => { if (ids.length < 8 && ids.indexOf(id) < 0) ids.push(id); });
    return ids.map((id) => items.find((it) => it.id === id)).filter(Boolean);
  }
  let mode = 'common';
  let cat = '';
  let query = '';

  function allItems() {
    const out = [];
    DS.getFeatures().forEach((g) => g.items.forEach((it) => out.push(Object.assign({ cat: g.cat }, it))));
    return out;
  }
  function featButton(it) {
    const inner = `<span class="hub-ic">${S.icon(it.icon)}</span><b>${esc(it.name)}</b>`;
    return it.action
      ? `<button type="button" class="hub-feat" data-act="${esc(it.action)}">${inner}</button>`
      : `<a class="hub-feat" href="${esc(it.route)}">${inner}</a>`;
  }
  function visibleItems() {
    let items = allItems();
    if (query) {
      const terms = query.toLowerCase().split(/\s+/).filter(Boolean);
      items = items.filter((it) => terms.every((t) => [it.cat, it.name, it.desc, (it.kw || []).join(' ')].join(' ').toLowerCase().indexOf(t) >= 0));
    } else if (cat) items = items.filter((it) => it.cat === cat);
    else if (mode === 'common') items = commonItems(items);
    return items;
  }
  function featGrid() {
    const items = visibleItems();
    if (!items.length) return `<p class="empty">找不到「${esc(query)}」。</p>`;
    return items.map(featButton).join('');
  }
  function sideNav() {
    const cats = DS.getFeatures().map((g) => g.cat);
    const btn = (id, label) => `<button type="button" class="hub-cat ${(!query && cat === id && (id || mode === 'common')) ? 'on' : ''}" data-cat="${esc(id)}">${esc(label)}</button>`;
    return btn('', '常用') + cats.map((c) => `<button type="button" class="hub-cat ${!query && cat === c ? 'on' : ''}" data-cat="${esc(c)}">${esc(c)}</button>`).join('');
  }

  function publicHome() {
    const wk = ['日', '一', '二', '三', '四', '五', '六'];
    const news = (S.CAMPUS_NEWS || []).slice(0, 8);
    const links = [
      ['東吳官網', 'https://www.scu.edu.tw/'],
      ['校園新聞', 'https://news.scu.edu.tw/'],
      ['招生資訊', 'https://entrance.exam.scu.edu.tw/'],
      ['圖書館', 'https://www.lib.scu.edu.tw/'],
      ['校務系統', '#/login']
    ];
    return `
      <section class="scu-hero">
        <img src="img/scu-logo.png" alt="">
        <div>
          <p>SOOCHOW UNIVERSITY</p>
          <h1>歡迎光臨東吳大學</h1>
          <p class="scu-motto">養天地正氣，法古今完人</p>
        </div>
        <a class="btn" href="#/login">進入校務系統</a>
      </section>
      <nav class="pub-links" aria-label="學校網站">${links.map(([name, url]) => url.startsWith('#') ? `<a href="${url}">${esc(name)}</a>` : `<a href="${url}" target="_blank" rel="noopener">${esc(name)}</a>`).join('')}</nav>
      <div class="scu-split">
        <section>
          <div class="sec-head"><h2>最新公告 <small>/ Latest Announcement</small></h2><a class="link-more" href="https://news.scu.edu.tw/" target="_blank" rel="noopener">更多</a></div>
          ${news.map((n) => {
            const day = wk[new Date(n.date + 'T00:00:00').getDay()];
            return `<a class="scu-ann" href="${n.url}" target="_blank" rel="noopener"><span><b>${day}</b>${esc(n.date.replace(/-/g, '/'))}</span><em>校園頭條</em><strong>${esc(n.title)}</strong></a>`;
          }).join('')}
        </section>
        <aside class="scu-side">
          <h2>參訪資訊</h2>
          <p><b>外雙溪校區</b><br>111002 臺北市士林區臨溪路 70 號<br>TEL 02-2881-9471</p>
          <p><b>城中校區</b><br>100006 臺北市中正區貴陽街一段 56 號<br>TEL 02-2311-1531</p>
          <a class="btn btn-primary" href="#/login">學生／教師登入</a>
        </aside>
      </div>
      <section class="pub-block">
        <div class="sec-head"><h2>學院</h2><a class="link-more" href="https://admissions.ladm.scu.edu.tw/academy" target="_blank" rel="noopener">各院系 ${S.icon('right')}</a></div>
        <div class="pub-cards">
          ${[
            ['人文社會學院', '外雙溪', '中文、歷史、哲學、政治、社會、社工、音樂', 'https://web-ch.scu.edu.tw/human'],
            ['外國語文學院', '外雙溪', '英文、日文、德文', 'https://web-ch.scu.edu.tw/foreign'],
            ['理學院', '外雙溪', '數學、物理、化學、微生物、心理', 'https://web-ch.scu.edu.tw/science'],
            ['法學院', '城中', '法律', 'https://www.law.scu.edu.tw/'],
            ['商學院', '城中', '經濟、會計、企管、國貿、財工、資管', 'https://www.ba.scu.edu.tw/'],
            ['巨量資料管理學院', '外雙溪', '資料科學', 'https://web-ch.scu.edu.tw/bigdata']
          ].map(([name, campus, depts, url]) => `<a class="pub-card" href="${url}" target="_blank" rel="noopener"><b>${esc(name)}</b><span>${esc(campus)}校區</span><small>${esc(depts)}</small></a>`).join('')}
        </div>
      </section>
      <section class="pub-block">
        <div class="sec-head"><h2>行政單位</h2></div>
        <div class="pub-cards pub-cards-sm">
          ${[
            ['學務處', 'https://web-ch.scu.edu.tw/student'],
            ['總務處', 'https://web-ch.scu.edu.tw/general'],
            ['研究發展處', 'https://web-ch.scu.edu.tw/research'],
            ['國際處', 'https://www.scu.edu.tw/icae/'],
            ['圖書館', 'https://www.lib.scu.edu.tw/'],
            ['招生組', 'https://entrance.exam.scu.edu.tw/'],
            ['會計室', 'https://web-ch.scu.edu.tw/account'],
            ['人事室', 'https://web-ch.scu.edu.tw/personnel']
          ].map(([name, url]) => `<a class="pub-card" href="${url}" target="_blank" rel="noopener"><b>${esc(name)}</b></a>`).join('')}
        </div>
      </section>`;
  }
  S.views.home = {
    tab: 'home', title: '首頁',
    render() {
      if (!S.readLogin()) return publicHome();
      const P = DS.getProfile(); const wk = S.semesterWeek();
      return `
      <div class="hub">
        <section class="hello hub-hello">
          <h1 tabindex="0">${greet(S.nowMin)}，${esc(P.name)}<span class="hello-date">${S.fmtDate(S.today)} ${S.NOW.time}${wk ? `・第 ${wk} 週` : ''}<br>${esc(S.SEMESTER.label)}</span></h1>
        </section>
        <nav class="hub-side" aria-label="功能選單">${sideNav()}</nav>
        <div class="hub-main">
          <form class="hub-search" id="hub-search">
            ${S.icon('search')}
            <input id="hub-q" type="search" placeholder="搜尋你想辦的事，例如：選課、宿舍、繳費、請假" value="${esc(query)}" aria-label="搜尋功能">
          </form>
          <section class="card hub-common" aria-labelledby="h-common">
            <div class="sec-head"><h2 id="h-common">${query ? '搜尋結果' : (cat || '常用功能')}</h2>
              <button type="button" class="btn btn-sm" id="hub-all">${mode === 'all' && !cat && !query ? '只看常用' : '全部功能'}</button>
            </div>
            <div class="hub-feats" id="hub-feats">${featGrid()}</div>
          </section>
          ${todayStrip()}
          <section class="card hub-week" aria-labelledby="h-tt">
            <div class="sec-head"><h2 id="h-tt">${S.icon('table')}我的課表</h2><a class="link-more" href="#/timetable">完整課表 ${S.icon('right')}</a></div>
            <div class="only-desk">${S.timetableSheet(S.myCourses())}</div>
            ${S.mobileWeek(S.myCourses())}
          </section>
        </div>
        <aside class="hub-rail">
          ${eventsSection()}
        </aside>
      </div>`;
    },
    after() {
      if (!S.readLogin()) return;
      const qEl = S.$('#hub-q');
      const paint = () => {
        const box = S.$('#hub-feats'); const title = S.$('#h-common'); const allBtn = S.$('#hub-all');
        if (!box) return;
        box.innerHTML = featGrid();
        if (title) title.textContent = query ? '搜尋結果' : (cat || '常用功能');
        if (allBtn) allBtn.textContent = mode === 'all' && !cat && !query ? '只看常用' : '全部功能';
        S.$$('.hub-cat').forEach((b) => { b.classList.toggle('on', !query && b.dataset.cat === cat && (cat || mode === 'common')); });
      };
      qEl.addEventListener('input', () => { query = qEl.value.trim(); paint(); });
      S.$('#hub-search').addEventListener('submit', (e) => { e.preventDefault(); query = qEl.value.trim(); paint(); });
      S.$('#hub-all').addEventListener('click', () => {
        query = ''; qEl.value = ''; cat = '';
        mode = mode === 'all' ? 'common' : 'all';
        paint();
      });
      S.$('.hub-side').addEventListener('click', (e) => {
        const b = e.target.closest('[data-cat]'); if (!b) return;
        query = ''; qEl.value = '';
        cat = b.dataset.cat;
        mode = cat ? 'all' : 'common';
        paint();
      });
    }
  };
})();
