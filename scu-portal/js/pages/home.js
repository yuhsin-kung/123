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
  /* 左側分類的中標題小字只顯示一行：放不下時只留完整放得下的中標題，後面空一格接「...」，不把詞切一半 */
  function fitCatSubs() {
    S.$$('.hub-cat small[data-subs]').forEach((el) => {
      const all = el.dataset.subs.split('・');
      el.textContent = all.join('・');
      if (!el.clientWidth || el.scrollWidth <= el.clientWidth) return;
      for (let n = all.length - 1; n >= 1; n--) {
        el.textContent = all.slice(0, n).join('・') + ' ...';   /* 英文句點貼在字底，不用中文字型會置中的「…」 */
        if (el.scrollWidth <= el.clientWidth) return;
      }
    });
  }
  function placeHubSide() {
    fitCatSubs();
    const side = S.$('.hub-side'); const hub = S.$('.hub'); const hero = S.$('.hub-hello');
    const main = S.$('.hub-main'); const rail = S.$('.hub-rail');
    if (!side || !hub || !hero || window.innerWidth < 900) {
      [side, hero].forEach((el) => { if (el) { el.style.left = ''; el.style.top = ''; el.style.width = ''; el.style.maxHeight = ''; el.style.gap = ''; } });
      [main, rail].forEach((el) => { if (el) el.style.marginTop = ''; });
      return;
    }
    const left = hub.getBoundingClientRect().left + 'px';
    hero.style.left = left;
    hero.style.width = hub.getBoundingClientRect().width + 'px';
    side.style.left = left;
    const gap = hero.offsetHeight + 12;
    side.style.top = (78 + gap) + 'px';
    side.style.maxHeight = `calc(100vh - ${78 + gap + 16}px)`; /* 依實際 top 算高度，最後一個類別才捲得到 */
    /* 按鈕間距依剩下的高度平均分配，讓選單大致填滿到畫面底部；最少 8px、最多 30px */
    const btns = side.children.length;
    if (btns > 1) {
      const avail = window.innerHeight - (78 + gap) - 24;
      const used = [...side.children].reduce((s, b) => s + b.offsetHeight, 0);
      side.style.gap = Math.max(8, Math.min(30, Math.floor((avail - used) / (btns - 1)))) + 'px';
    }
    /* 中間／右側欄的頂端對齊左側選單的頂端（不再多空一段） */
    const push = Math.max(0, 78 + gap - (hub.getBoundingClientRect().top + window.scrollY)) + 'px';
    if (main) main.style.marginTop = push;
    if (rail) rail.style.marginTop = push;
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
    <ellipse class="ab-shadow" cx="50" cy="111" rx="22" ry="4" fill="#f3dcd9"/>
    <g class="ab-body">
    <line x1="50" y1="14" x2="50" y2="4" stroke="#e3b9b2" stroke-width="3" stroke-linecap="round"/>
    <circle class="ab-light" cx="50" cy="4" r="4" fill="#8b1a1a"/>
    <rect x="10" y="30" width="8" height="18" rx="4" fill="#eac8c3"/>
    <rect x="82" y="30" width="8" height="18" rx="4" fill="#eac8c3"/>
    <g class="ab-arm"><path d="M74 68 Q90 62 88 46" stroke="#f3dcd9" stroke-width="7" fill="none" stroke-linecap="round"/>
    <circle cx="88" cy="44" r="6" fill="#fff" stroke="#f3dcd9" stroke-width="2"/></g>
    <path d="M26 70 Q14 76 14 90" stroke="#f3dcd9" stroke-width="7" fill="none" stroke-linecap="round"/>
    <rect x="34" y="92" width="10" height="14" rx="5" fill="#fff" stroke="#f3dcd9" stroke-width="2"/>
    <rect x="56" y="92" width="10" height="14" rx="5" fill="#fff" stroke="#f3dcd9" stroke-width="2"/>
    <rect x="26" y="62" width="48" height="34" rx="17" fill="#fff" stroke="#f3dcd9" stroke-width="2"/>
    <circle cx="50" cy="79" r="6" fill="#8b1a1a"/>
    <rect x="20" y="10" width="60" height="50" rx="25" fill="#fff" stroke="#f3dcd9" stroke-width="2"/>
    <g class="ab-eyes"><circle cx="38" cy="36" r="4" fill="#2a2320"/>
    <circle cx="62" cy="36" r="4" fill="#2a2320"/></g>
    <circle class="ab-cheek" cx="30" cy="42" r="3.5" fill="#f6b8c6" opacity=".8"/>
    <circle class="ab-cheek" cx="70" cy="42" r="3.5" fill="#f6b8c6" opacity=".8"/>
    <path d="M44 42 Q50 47 56 42" stroke="#2a2320" stroke-width="2.5" fill="none" stroke-linecap="round"/>
    </g>
  </svg>`;
  S.ASLA_MASCOT = ASLA_MASCOT;   /* 其他頁右下角的阿斯拉小機器人也用這張（asla.js） */
  const ASLA_PROMO_CHIPS = ['我要申請宿舍', '怎麼退選課程？', '畢業需要多少學分？'];
  function aslaPromoCard() {
    return `<section class="card asla-promo" aria-labelledby="h-asla-promo">
      <div class="asla-promo-bot">${ASLA_MASCOT}</div>
      <div class="asla-promo-body">
        <div class="asla-promo-title"><h2 id="h-asla-promo">阿斯拉 AI 助手</h2></div>
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

  let mode = 'common';
  let cat = '';
  let query = '';

  /* 中間卡片一律用「中標題＋細項按鈕」的樣式（跟全部功能頁、左側分類同一套 SCU.MENU） */
  const menuTree = () => (S.menuTree ? S.menuTree() : []);
  const group = (title, leaves, withCtx) => `<div class="mc-group"><h3>${esc(title)}</h3><div class="mc-leaves">${leaves.map((l) => S.menuLeaf(l, !!withCtx)).join('')}</div></div>`;
  const wrap = (html) => `<div class="hub-menu">${html}</div>`;

  /* 還沒有使用紀錄時先推薦的細項（名稱要跟 SCU.MENU 的細項一致） */
  const COMMON_SEED = ['網路選課', '功課表查詢', '學期成績', '註冊繳費', '宿舍申請', '線上請假', '可申請查詢', '教室資訊查詢', '期末退修申請', '活動報名'];
  const COMMON_MAX = 10;   /* 桌機一排 5 個，剛好兩排 */
  function commonMenu() {
    const all = []; const seen = {};
    menuTree().forEach((c) => c.groups.forEach((g) => g.leaves.forEach((l) => { if (!seen[l.label]) { seen[l.label] = 1; all.push(l); } })));
    /* 最多 10 個：點過的依次數排前面，不夠的用 COMMON_SEED 補滿；排成等寬格子 */
    const counts = DS.leafUse();
    const list = all.filter((l) => counts[l.label]).sort((a, b) => counts[b.label] - counts[a.label]).slice(0, COMMON_MAX);
    COMMON_SEED.forEach((n) => { const l = all.find((x) => x.label === n); if (l && list.length < COMMON_MAX && list.indexOf(l) < 0) list.push(l); });
    return wrap(`<div class="common-grid">${list.map((l) => S.menuLeaf(l, true)).join('')}</div>`);
  }
  /* 左側選了某一類：只顯示那一類 */
  function catMenu() {
    const c = menuTree().find((x) => x.name === cat); if (!c) return '';
    return wrap(c.groups.map((g) => group(g.title, g.leaves)).join(''));
  }
  /* 搜尋：比對分類、中標題、細項與功能關鍵字，結果依分類分組 */
  function searchMenu() {
    const terms = query.toLowerCase().split(/\s+/).filter(Boolean);
    const html = menuTree().map((c) => {
      const hits = [];
      c.groups.forEach((g) => g.leaves.forEach((l) => { const s = (c.name + ' ' + g.title + ' ' + l.text).toLowerCase(); if (terms.every((t) => s.indexOf(t) >= 0)) hits.push(l); }));
      return hits.length ? group(c.name, hits, true) : '';
    }).join('');
    return html ? wrap(html) : `<p class="empty">找不到「${esc(query)}」。</p>`;
  }
  function featGrid() {
    if (query) return searchMenu();
    return cat ? catMenu() : commonMenu();
  }
  function sideNav() {
    /* 每個分類底下用小字列出它的中標題，讓人不用點開就知道裡面有什麼 */
    const btn = (id, label, sub) => `<button type="button" class="hub-cat ${(!query && cat === id && (id || mode === 'common')) ? 'on' : ''}" data-cat="${esc(id)}"><b>${esc(label)}</b><small>${esc(sub)}</small></button>`;
    return btn('', '常用', '依你的使用自動排序') + (S.MENU || []).map((c) => {
      const subs = c.groups.map((g) => g[0]).join('・');
      return `<button type="button" class="hub-cat ${!query && cat === c.name ? 'on' : ''}" data-cat="${esc(c.name)}" title="${esc(subs)}"><b>${esc(c.name)}</b><small data-subs="${esc(subs)}">${esc(subs)}</small></button>`;
    }).join('');
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
        <div class="hub-main ${cat && !query ? 'cat-mode' : ''}">
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
        /* 選了左側某一類：中間只留那一類的內容（搜尋框、阿斯拉卡片先收起來；點「常用」就回來） */
        S.$('.hub-main').classList.toggle('cat-mode', !!cat && !query);
        if (S.syncAslaDot) S.syncAslaDot();   /* 阿斯拉卡片收起來時，右下角機器人要出現 */
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
        window.scrollTo({ top: 0 });
      });
    }
  };
})();
