/* =========================================================================
 * pages/home.js — 首頁（#/home）
 * -------------------------------------------------------------------------
 * 版面（示意圖）：左側功能選單、上方打字搜尋、搜尋下方阿斯拉導引卡、
 *   再下面常用功能（可改看全部）、右側上方今天課表、右側下方行事曆。
 * ========================================================================= */
(function () {
  'use strict';
  const S = window.SCU; const esc = S.esc; const DS = S.DS;

  /* 桌機版「晚安，王小明」跟左側功能選單整塊固定住，滑動整頁時都不會動，
     只有中間／右側欄（常用功能、今天課表、行事曆…）會捲動。
     left／width 用 JS 量 .hub 實際邊界，比純 CSS 的 100vw 精準（100vw 在有捲軸時會多算捲軸寬度）。
     中間／右側欄的 margin-top 讓出「晚安」那排固定佔用的高度，不會被蓋住。 */
  function placeHubSide() {
    const side = S.$('.hub-side'); const hub = S.$('.hub'); const hero = S.$('.hub-hello');
    const main = S.$('.hub-main'); const rail = S.$('.hub-rail');
    if (!side || !hub || !hero || window.innerWidth < 900) {
      [side, hero].forEach((el) => { if (el) { el.style.left = ''; el.style.top = ''; el.style.width = ''; el.style.maxHeight = ''; } });
      [main, rail].forEach((el) => { if (el) el.style.marginTop = ''; });
      return;
    }
    const left = hub.getBoundingClientRect().left + 'px';
    hero.style.left = left;
    hero.style.width = hub.getBoundingClientRect().width + 'px';
    side.style.left = left;
    const gap = hero.offsetHeight + 20;
    side.style.top = (78 + gap) + 'px';
    side.style.maxHeight = `calc(100vh - ${78 + gap + 16}px)`; /* 依實際 top 算高度，最後一個類別才捲得到 */
    if (main) main.style.marginTop = gap + 'px';
    if (rail) rail.style.marginTop = gap + 'px';
  }
  window.addEventListener('resize', placeHubSide);

  function greet(min) { return min < 11 * 60 ? '早安' : min < 14 * 60 ? '午安' : min < 18 * 60 ? '午後好' : '晚安'; }
  function inSemester(d) { return d >= S.SEMESTER.start && d <= S.SEMESTER.end; }
  function dayClasses(d) { return (!S.holidayOn(d) && inSemester(d)) ? S.classesOn(d) : []; }

  /* 往後找下一個有課的日子（最多 21 天） */
  function nextClassDay(from) {
    for (let i = 1; i <= 21; i++) { const d = S.addDays(from, i); const cl = dayClasses(d); if (cl.length) return { d, first: cl[0], n: cl.length }; }
    return null;
  }

  function todayScheduleCard() {
    const d = S.today; const wd = S.weekday(d); const hol = S.holidayOn(d);
    const list = dayClasses(d);
    let body;
    if (!list.length) {
      const why = hol ? `今天是「${esc(hol.title)}」，沒有課` : (wd === 0 || wd === 6) ? '今天是週末，沒有課' : !inSemester(d) ? '目前不在上課期間' : '今天沒有排課';
      const nx = nextClassDay(d);
      body = `<p class="empty">${why}${nx ? `，下一堂 ${S.fmtDate(nx.d)} ${nx.first.startT} ${esc(nx.first.c.name)}` : ''}</p>`;
    } else {
      body = `<div class="m-classes">${list.map((x) => {
        const meta = [x.s.room || x.c.room, x.c.teacher].filter(Boolean).join(' · ');
        return `<article class="m-class"><span class="m-per">${esc(x.startT)}</span><div><b>${esc(x.c.name)}</b><small>${esc(meta)}</small></div></article>`;
      }).join('')}</div>`;
    }
    return `<section class="card sec-today-tt" aria-labelledby="h-today-tt" style="--n:${list.length}">
      <div class="sec-head"><h2 id="h-today-tt">${S.icon('table')}今天課表</h2><a class="link-more" href="#/timetable">完整課表 ${S.icon('right')}</a></div>
      ${body}</section>`;
  }

  const ASLA_MASCOT = `<svg viewBox="0 0 100 116" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
    <ellipse cx="50" cy="111" rx="22" ry="4" fill="#f3dcd9"/>
    <line x1="50" y1="14" x2="50" y2="4" stroke="#e3b9b2" stroke-width="3" stroke-linecap="round"/>
    <circle cx="50" cy="4" r="4" fill="#8b1a1a"/>
    <rect x="10" y="30" width="8" height="18" rx="4" fill="#eac8c3"/>
    <rect x="82" y="30" width="8" height="18" rx="4" fill="#eac8c3"/>
    <path d="M74 68 Q90 62 88 46" stroke="#f3dcd9" stroke-width="7" fill="none" stroke-linecap="round"/>
    <circle cx="88" cy="44" r="6" fill="#fff" stroke="#f3dcd9" stroke-width="2"/>
    <path d="M26 70 Q14 76 14 90" stroke="#f3dcd9" stroke-width="7" fill="none" stroke-linecap="round"/>
    <rect x="34" y="92" width="10" height="14" rx="5" fill="#fff" stroke="#f3dcd9" stroke-width="2"/>
    <rect x="56" y="92" width="10" height="14" rx="5" fill="#fff" stroke="#f3dcd9" stroke-width="2"/>
    <rect x="26" y="62" width="48" height="34" rx="17" fill="#fff" stroke="#f3dcd9" stroke-width="2"/>
    <circle cx="50" cy="79" r="6" fill="#8b1a1a"/>
    <rect x="20" y="10" width="60" height="50" rx="25" fill="#fff" stroke="#f3dcd9" stroke-width="2"/>
    <circle cx="38" cy="36" r="4" fill="#2a2320"/>
    <circle cx="62" cy="36" r="4" fill="#2a2320"/>
    <circle cx="30" cy="42" r="3.5" fill="#f6b8c6" opacity=".8"/>
    <circle cx="70" cy="42" r="3.5" fill="#f6b8c6" opacity=".8"/>
    <path d="M44 42 Q50 47 56 42" stroke="#2a2320" stroke-width="2.5" fill="none" stroke-linecap="round"/>
  </svg>`;
  const ASLA_PROMO_CHIPS = ['我要申請宿舍', '怎麼退選課程？', '畢業需要多少學分？'];
  function aslaPromoCard() {
    return `<section class="card asla-promo" aria-labelledby="h-asla-promo">
      <div class="asla-promo-bot">${ASLA_MASCOT}</div>
      <div class="asla-promo-body">
        <div class="asla-promo-title"><h2 id="h-asla-promo">阿斯拉 AI 助手</h2><span class="asla-beta">Beta</span></div>
        <p class="asla-promo-lead">不知道該去哪裡辦？</p>
        <p class="asla-promo-desc">告訴我你的問題，我幫你找功能、查資料！</p>
        <div class="asla-promo-chips">${ASLA_PROMO_CHIPS.map((c) => `<button type="button" data-q="${esc(c)}">「${esc(c)}」</button>`).join('')}</div>
        <button type="button" class="btn asla-promo-cta" id="asla-promo-open">開始詢問 <span aria-hidden="true">→</span></button>
      </div>
    </section>`;
  }

  function eventsSection() {
    const evs = S.upcomingEvents(8);
    /* 時間軸：左側日期、中間線與類別色點、右側標題＋「類別・倒數」一行 */
    const T = S.DS.getEventTypes();
    const rows = evs.map((e) => {
      const cd = S.countdown(e);
      const until = e.end && e.end !== e.start ? `至 ${S.fmtDate(e.end, false)}・` : '';
      return `<a class="tl-item ${cd.urgent ? 'is-urgent' : ''} ${cd.state === 'ongoing' ? 'is-ongoing' : ''}" href="${esc(e.route || '#/calendar')}">
        <span class="tl-date">${S.fmtDate(e.start, false)}</span><span class="tl-rail"><span class="tl-dot ${T[e.type].cls}"></span></span>
        <span class="tl-body"><b>${esc(e.title)}</b><small>${T[e.type].name}・${until}<span class="tl-when">${esc(cd.label)}</span></small></span></a>`;
    }).join('');
    return `<section class="card sec-events" aria-labelledby="h-ev">
      <div class="sec-head"><h2 id="h-ev">${S.icon('calendar')}行事曆</h2><a class="link-more" href="#/calendar">看全部 ${S.icon('right')}</a></div>
      ${rows ? `<div class="tl">${rows}</div>` : '<div class="empty">最近沒有全校事務。</div>'}</section>`;
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
          ${aslaPromoCard()}
          <section class="card hub-common" aria-labelledby="h-common">
            <div class="sec-head"><h2 id="h-common">${query ? '搜尋結果' : (cat || '常用功能')}</h2>
              <a class="btn btn-sm" id="hub-all" href="#/more">全部功能</a>
            </div>
            <div class="hub-feats" id="hub-feats">${featGrid()}</div>
          </section>
        </div>
        <aside class="hub-rail">
          ${todayScheduleCard()}
          ${eventsSection()}
        </aside>
      </div>`;
    },
    after() {
      if (!S.readLogin()) return;
      placeHubSide();
      const qEl = S.$('#hub-q');
      const paint = () => {
        const box = S.$('#hub-feats'); const title = S.$('#h-common');
        if (!box) return;
        box.innerHTML = featGrid();
        if (title) title.textContent = query ? '搜尋結果' : (cat || '常用功能');
        S.$$('.hub-cat').forEach((b) => { b.classList.toggle('on', !query && b.dataset.cat === cat && (cat || mode === 'common')); });
      };
      S.$('.asla-promo').addEventListener('click', (e) => {
        const chip = e.target.closest('[data-q]');
        if (chip) { S.openAsla(chip.dataset.q); return; }
        if (e.target.closest('#asla-promo-open')) S.openAsla();
      });
      qEl.addEventListener('input', () => { query = qEl.value.trim(); paint(); });
      S.$('#hub-search').addEventListener('submit', (e) => { e.preventDefault(); query = qEl.value.trim(); paint(); });
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
