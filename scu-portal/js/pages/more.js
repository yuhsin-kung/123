/* =========================================================================
 * pages/more.js — 更多（#/more）、功能示範頁（#/p/功能代號）、示範設定（#/settings）
 * -------------------------------------------------------------------------
 * 更多：依類別列出所有站內功能（資料在 data-features.js），可用關鍵字篩選。
 *       已完整建置的頁面直接前往；尚未建置的功能進入站內「示範頁」，不連外部網站。
 * 示範頁：通用版型（說明、之後可辦理的項目、相關行事曆日期），
 *         另有專屬內容：公告、校園信箱、學雜費繳費、期中退選、個人資料、諮商預約。
 * 示範設定：切換示範日期時間（改網址 ?date=&time=）、重設本機示範資料、顯示資料來源。
 * ========================================================================= */
(function () {
  'use strict';
  const S = window.SCU; const esc = S.esc; const DS = S.DS; const st = S.state;

  /* ---------------- 更多：11 大類字卡（資料在 data-features.js 的 SCU.MENU） ---------------- */
  let openCat = -1;   /* 目前展開的字卡；一次只展開一張 */
  function target(to) {
    if (to.indexOf('act:') === 0) {
      const act = to.slice(4); let feat = null;
      DS.getFeatures().forEach((g) => g.items.forEach((it) => { if (it.action === act) feat = it; }));
      return { act, feat };
    }
    if (to.charAt(0) === '#') return { route: to, feat: DS.featureForHash(to) };
    const f = DS.getFeature(to);
    return { route: f ? f.route : '#/more', feat: f };
  }
  /* 把 SCU.MENU 攤平成 [{ title, leaves:[{ label, route, text }] }]，text 給搜尋用（含功能關鍵字） */
  function menu() {
    return (S.MENU || []).map((c, ci) => ({
      ci, name: c.name, icon: c.icon,
      groups: c.groups.map(([title, rest]) => ({
        title,
        leaves: (Array.isArray(rest) ? rest : [[title, rest]]).map(([label, to]) => {
          const t = target(to); const f = t.feat || {};
          return { label, group: title, cat: c.name, fid: t.feat ? t.feat.id : '', route: t.route, act: t.act, text: [label, f.name, f.desc, (f.kw || []).join(' ')].join(' ').toLowerCase() };
        })
      }))
    }));
  }
  /* 細項上方的灰色小字：一律標中標題；中標題跟細項同名（例如宿舍申請）就改標大分類，避免重複 */
  const ctxOf = (l) => (l.group && l.group !== l.label ? l.group : l.cat) || '';
  /* 細項按鈕：一般是站內連結；act: 開頭的是站內動作（例如打開阿斯拉）。
   * withCtx：常用、搜尋結果這種不同中標題混在一起的地方，在名稱上方用灰色小字標出它屬於哪裡 */
  function leaf(l, withCtx) {
    const ctx = withCtx === true ? ctxOf(l) : '';
    const inner = `<span class="mc-leaf-t">${ctx ? `<small>${esc(ctx)}</small>` : ''}${esc(l.label)}</span><span class="mc-arr" aria-hidden="true">↗</span>`;
    const k = `data-leaf="${esc(l.label)}"`;
    return l.act ? `<button type="button" class="mc-leaf" ${k} data-act="${esc(l.act)}">${inner}</button>` : `<a class="mc-leaf" ${k} href="${esc(l.route)}">${inner}</a>`;
  }
  /* 任何頁面點了細項就記一次，首頁「最近常用」用 */
  document.addEventListener('click', (e) => { const l = e.target.closest('.mc-leaf[data-leaf]'); if (l) DS.bumpLeaf(l.dataset.leaf); });
  S.menuTree = menu; S.menuLeaf = leaf;   /* 首頁左側分類也用這份 */

  /* 功能（SCU.FEATURES 的 id）在新分類裡的顯示名稱與大分類，示範頁標題和阿斯拉的按鈕都用這個，跟選單一致。
   * 名稱依序判斷：
   *   1. 細項整組佔中標題（不跟別的功能共用、也不是「其他」）→ 用中標題，幾組就用「／」連起來
   *      例如 double →「雙輔跨作業」、intern →「實習／證照獎勵」
   *   2. 只有一個細項 → 用細項名稱，例如 emergency →「急難救助申請」
   *   3. 其他情況沿用原本的名稱，例如 scholarship →「獎助學金」
   * 不在新分類裡的功能（期中退選、公告…）回傳 null，沿用原本的名稱與類別。 */
  let infoMap = null;
  function menuInfo(id) {
    if (!infoMap) {
      infoMap = {};
      menu().forEach((c) => c.groups.forEach((g) => {
        const owners = new Set(g.leaves.map((l) => l.fid));
        g.leaves.forEach((l) => {
          if (!l.fid) return;
          const e = infoMap[l.fid] || (infoMap[l.fid] = { cat: c.name, groups: [], labels: [], ownsAll: true });
          if (e.groups.indexOf(g.title) < 0) e.groups.push(g.title);
          e.labels.push(l.label);
          if (owners.size > 1 || g.title === '其他') e.ownsAll = false;
        });
      }));
    }
    const e = infoMap[id]; const f = DS.getFeature(id);
    if (!e || !f) return null;
    const name = e.ownsAll ? e.groups.join('／') : e.labels.length === 1 ? e.labels[0] : f.name;
    return { cat: e.cat, name };
  }
  S.menuInfo = menuInfo;
  /* 功能的顯示用資料：名稱與類別換成新分類的，其餘（網址、說明、關鍵字）照舊 */
  S.featureView = (f) => { if (!f) return f; const i = menuInfo(f.id); return i ? Object.assign({}, f, { name: i.name, catName: i.cat }) : f; };
  function card(c, open, groups) {
    const num = String(c.ci + 1).padStart(2, '0');
    const summary = c.groups.map((g) => g.title).join('・');
    const body = open ? `<div class="mc-body" id="mc-body-${c.ci}">${groups.map((g) => `<div class="mc-group"><h3>${esc(g.title)}</h3>
        <div class="mc-leaves">${g.leaves.map(leaf).join('')}</div></div>`).join('')}</div>` : '';
    return `<section class="mcard ${open ? 'open' : ''}">
      <button type="button" class="mc-head" data-cat="${c.ci}" aria-expanded="${open}" aria-controls="mc-body-${c.ci}">
        <span class="mc-num">${num}</span><span class="mc-ic">${S.icon(c.icon)}</span>
        <span class="mc-t"><b>${esc(c.name)}</b><small>${esc(summary)}</small></span>
        <span class="mc-bg" aria-hidden="true">${num}</span></button>${body}</section>`;
  }
  function renderTiles(q) {
    const terms = String(q || '').trim().toLowerCase().split(/\s+/).filter(Boolean);
    const cats = menu();
    if (!terms.length) return `<div class="mcards">${cats.map((c) => card(c, c.ci === openCat, c.groups)).join('')}</div>`;
    /* 搜尋：類別或中標題對到 → 整組顯示；否則只留對到的細項。有結果的字卡全部展開 */
    const hit = (s) => terms.every((t) => s.indexOf(t) >= 0);
    const html = cats.map((c) => {
      const groups = c.groups.map((g) => {
        const head = (c.name + ' ' + g.title).toLowerCase();
        return { title: g.title, leaves: g.leaves.filter((l) => hit(head + ' ' + l.text)) };
      }).filter((g) => g.leaves.length);
      return groups.length ? card(c, true, groups) : '';
    }).join('');
    return html ? `<div class="mcards">${html}</div>` : `<div class="empty">找不到「${esc(q)}」。<br><button class="btn btn-sm btn-primary" type="button" data-act="open-asla" data-q="${esc(q)}">問問阿斯拉</button></div>`;
  }
  /* 展開的字卡留在原本那一排的開頭、佔滿整排；同一排的其他字卡往下推到下一排。
   * 用 CSS order 排，欄數（1／2／3）直接讀 grid 算出來的欄數，視窗寬度改變時重排。 */
  function layoutOpen() {
    const grid = document.querySelector('#ftiles .mcards'); if (!grid) return;
    const cards = [...grid.children];
    const opened = cards.filter((c) => c.classList.contains('open'));
    if (opened.length !== 1 || cards.length !== (S.MENU || []).length) return;   /* 沒展開或搜尋中：照原順序 */
    const oi = cards.indexOf(opened[0]);
    const cols = getComputedStyle(grid).gridTemplateColumns.split(' ').filter(Boolean).length || 1;
    const rowStart = Math.floor(oi / cols) * cols;
    cards.forEach((c, k) => { c.style.order = k < rowStart ? k : (k === oi ? rowStart : k + 1); });
  }
  window.addEventListener('resize', layoutOpen);

  S.views.more = {
    tab: 'more', title: '全部功能',
    render(p) {
      const o = parseInt(p.get('open'), 10); if (o >= 1 && o <= (S.MENU || []).length) openCat = o - 1;
      return `<div class="page-head"><div><h1>全部功能</h1><p class="muted small">全部都在站內完成，不用跳到其他系統</p></div></div>
        <div class="searchbar">${S.icon('search')}<input id="more-q" type="search" placeholder="找功能：就貸、宿舍、請假、選課清單…" value="${esc(p.get('q') || '')}" aria-label="搜尋功能"></div>
        <div id="ftiles">${renderTiles(p.get('q'))}</div>`;
    },
    after() {
      const i = S.$('#more-q'), box = S.$('#ftiles');
      layoutOpen();
      i.addEventListener('input', () => { box.innerHTML = renderTiles(i.value); layoutOpen(); });
      box.addEventListener('click', (e) => {
        const h = e.target.closest('.mc-head'); if (!h) return;
        const ci = +h.dataset.cat;
        if (i.value.trim()) { i.value = ''; openCat = ci; }       /* 搜尋中點字卡：清掉搜尋，只展開這張 */
        else openCat = openCat === ci ? -1 : ci;
        box.innerHTML = renderTiles('');
        layoutOpen();
        const el = box.querySelector(`[data-cat="${ci}"]`); if (el) { el.focus(); if (openCat === ci) el.scrollIntoView({ block: 'nearest', behavior: 'smooth' }); }
      });
    }
  };

  /* ---------------- 功能示範頁 ---------------- */
  function relatedEvents(id) {
    const evs = DS.getEvents().filter((e) => e.route === '#/p/' + id && S.eventEnd(e) >= S.today);
    return evs.length ? `<section class="card section"><h3>相關日期</h3>${evs.map((e) => { const cd = S.countdown(e); return `<p class="ev-mini">${S.evTag(e)} <b>${esc(e.title)}</b> <span class="small muted">${S.eventRange(e)}</span> <span class="pill-mini ${cd.urgent ? 'bad' : ''}">${esc(cd.label)}</span></p>`; }).join('')}</section>` : '';
  }
  const special = {
    news() {
      return `<div class="card flush clist">${DS.getNews().map((n) => `<div class="crow"><div class="crow-day"><b>${S.fmtDate(n.date, false)}</b><small>${esc(n.unit)}</small></div>
        <div class="crow-main"><span class="pill-mini">${esc(n.tag)}</span> ${esc(n.title)}</div></div>`).join('')}</div>`;
    },
    mail() {
      const P = DS.getProfile();
      return `<p class="small muted">帳號：${esc(P.studentId)}（示範收件匣）</p><div class="card flush clist">${DS.getMails().map((m) => `<div class="crow ${m.unread ? 'unread' : ''}"><div class="crow-day"><b>${S.fmtDate(m.date, false)}</b></div>
        <div class="crow-main"><b>${esc(m.from)}</b><br><span class="${m.unread ? '' : 'muted'}">${esc(m.title)}</span></div>${m.unread ? '<span class="dot-unread" aria-label="未讀"></span>' : ''}</div>`).join('')}</div>`;
    },
    fee() {
      const e = DS.getEvents().find((x) => x.id === 'fee'); const cd = e ? S.countdown(e) : null;
      return `<section class="card bill"><div class="sec-head"><h3>${S.SEMESTER.code} 學雜費繳費單</h3><span class="pill-mini bad">未繳費</span></div>
        <div class="bill-amt">NT$ 52,340</div>
        <p class="small">學費 38,120・雜費 12,720・平安保險 470・學生會費 1,030（示範金額）</p>
        ${e ? `<p class="small">繳費截止：<b>${S.fmtDate(e.start)}</b>（${esc(cd.label)}）</p>` : ''}
        <div class="row-btns"><button class="btn btn-primary btn-sm" type="button" data-act="demo-only">下載繳費單</button><button class="btn btn-sm" type="button" data-act="demo-only">繳費方式說明</button></div></section>`;
    },
    'midterm-drop'() {
      const e = DS.getEvents().find((x) => x.id === 'middrop'); const open = e && e.start <= S.today && S.eventEnd(e) >= S.today;
      const cd = e ? S.countdown(e) : null;
      const list = S.myCourses();
      return `<div class="notice ${open ? 'good' : ''}">${S.icon('calendar')}<span>開放期間：<b>${e ? S.eventRange(e) : '—'}</b>・${open ? '現在可以申請' : esc(cd ? cd.label : '')}${open ? '' : '（開放後按鈕才能使用；可用「示範設定」把日期切到期間內試試）'}</span></div>
        <div class="card flush clist">${list.map((c) => `<div class="crow"><div class="crow-main"><b>${esc(c.name)}</b> <span class="code">${c.code}</span><br><span class="small muted">${S.slotText(c)}・${c.credits} 學分</span></div>
          <button class="btn btn-sm" type="button" data-act="mid-drop" data-code="${c.code}" ${open ? '' : 'disabled'}>期中退選</button></div>`).join('') || '<div class="empty">課表是空的。</div>'}</div>
        ${st.withdrawn.length ? `<p class="small">已期中退選（W）：${st.withdrawn.map((c) => esc((DS.getCourse(c) || {}).name || c)).join('、')}</p>` : ''}`;
    },
    profile() {
      const P = DS.getProfile();
      return `<section class="card"><dl class="kv"><dt>姓名</dt><dd>${esc(P.name)}</dd><dt>學號</dt><dd>${esc(P.studentId)}</dd><dt>學制</dt><dd>${esc(P.program)}</dd><dt>系所</dt><dd>${esc(P.dept)}</dd><dt>年級／班別</dt><dd>${P.grade} 年級 ${esc(P.cls)} 班</dd><dt>校區</dt><dd>${esc(P.campus)}</dd></dl>
        <p class="tiny muted">示範登入身分，設定在 js/profile.js；之後由登入後的後端資料取代。</p></section>`;
    },
    counsel() {
      return `<div class="notice warn">${S.icon('alert')}<span>若有立即危險，請先撥打 <b>119</b> 或 <b>110</b>。</span></div>`;
    }
  };
  S.views.p = {
    tab: 'more',
    title: (sub) => (S.featureView(DS.getFeature(sub)) || { name: '功能' }).name,
    render(p, sub) {
      const f = S.featureView(DS.getFeature(sub));
      if (!f) return `<div class="empty">找不到這個功能。<br><a class="btn btn-sm" href="#/more">回全部功能</a></div>`;
      const sp = special[f.id] ? special[f.id]() : '';
      const subs = f.subs && f.subs.length ? `<section class="card section"><h3>這一頁之後可以辦理</h3><div class="clist">${f.subs.map((s) => `<button type="button" class="sub-row" data-act="demo-only"><span>${esc(s)}</span>${S.icon('right')}</button>`).join('')}</div></section>` : '';
      return `<a class="back" href="#/more">${S.icon('back')}全部功能</a>
        <div class="page-head"><div class="ph-ic">${S.icon(f.icon)}</div><div><h1>${esc(f.name)}</h1><p class="muted small">${esc(f.catName)}・${esc(f.desc)}</p></div></div>
        ${sp}${subs}${relatedEvents(f.id)}
        <p class="tiny muted demo-note">此頁為示範頁，內容與資料皆為虛構；完整功能待後續建置。</p>`;
    }
  };

  /* ---------------- 示範設定 ---------------- */
  S.views.settings = {
    tab: 'more', title: '示範設定',
    render() {
      const presets = [['2026-09-30', '10:30', '上課中（預設）'], ['2026-09-30', '13:00', '午休，下一堂快開始'], ['2026-09-30', '18:30', '今天課都上完了'], ['2026-10-03', '10:00', '週六（沒有課）'], ['2026-10-09', '10:00', '國慶日補假'], ['2026-11-20', '09:00', '期中退選期間']];
      const P = DS.getProfile();
      return `<a class="back" href="#/more">${S.icon('back')}全部功能</a>
        <div class="page-head"><div><h1>示範設定</h1><p class="muted small">給展示用：切換「今天」的日期時間，網站其他頁會跟著變</p></div></div>
        <section class="card"><h3>示範時間</h3>
          <p class="small">目前：<b>${S.today} ${S.NOW.time}</b>（${S.NOW.fromUrl ? '由網址參數指定' : '這台電腦的系統時間'}）</p>
          <form id="demo-time" class="filters"><label>日期<input type="date" name="date" value="${S.today}"></label><label>時間<input type="time" name="time" value="${S.NOW.time}"></label>
            <button class="btn btn-primary btn-sm" type="submit">套用</button><button class="btn btn-sm" type="button" data-act="demo-time-reset">回到預設</button></form>
          <div class="chips" style="margin-top:10px">${presets.map((x) => `<button type="button" class="chip" data-act="demo-time" data-date="${x[0]}" data-time="${x[1]}">${x[2]}</button>`).join('')}</div>
          <p class="tiny muted">也可直接在網址加上 <code>?date=2026-10-05&amp;time=09:00</code>。</p></section>
        <section class="card section"><h3>示範資料</h3>
          <p class="small">課表、選課車、名額變化只存在這台電腦的瀏覽器（localStorage）。</p>
          <button class="btn btn-sm" type="button" data-act="demo-reset">重設為初始示範資料</button>
          <button class="btn btn-sm" type="button" data-act="demo-conflict">載入「衝堂」示範選課車</button></section>
        <section class="card section"><h3>登入身分與資料來源</h3>
          <p class="small">${esc(P.name)}・${esc(P.program)}・${esc(P.dept)} ${P.grade} 年級 ${esc(P.cls)} 班（js/profile.js）</p>
          <p class="small">資料來源：<code>${esc(DS.source)}</code>（js/data-source.js；之後可改接 Python 後端 API）</p></section>`;
    },
    after() {
      S.$('#demo-time').addEventListener('submit', (e) => { e.preventDefault(); const f = e.target; gotoTime(f.date.value, f.time.value); });
    }
  };
  function gotoTime(date, time) {
    const q = new URLSearchParams(); if (date) q.set('date', date); if (time) q.set('time', time);
    location.href = location.pathname + (q.toString() ? '?' + q.toString() : '') + '#/home';
  }

  const A = S.actions;
  A['demo-only'] = () => S.toast('示範頁：此項目尚未建置');
  A['demo-time'] = (t) => gotoTime(t.dataset.date, t.dataset.time);
  A['demo-time-reset'] = () => gotoTime('', '');
  A['demo-reset'] = () => { if (confirm('把課表、選課車恢復成初始示範資料？')) { S.resetDemo(); S.toast('已重設示範資料'); S.refresh(); } };
  A['demo-conflict'] = () => { S.loadConflictDemo(); S.go('#/course?tab=cart'); };
  A['mid-drop'] = (t) => {
    const c = t.dataset.code; const course = DS.getCourse(c);
    if (!confirm(`確定期中退選「${course.name}」？（示範：成績單註記 W）`)) return;
    st.timetable = st.timetable.filter((x) => x !== c); st.withdrawn.push(c);
    st.seatDelta[c] = (st.seatDelta[c] || 0) - 1; S.save(); S.toast('已期中退選：' + course.name); S.refresh();
  };
})();
