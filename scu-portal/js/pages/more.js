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

  /* ---------------- 更多 ---------------- */
  function tile(it) {
    const inner = `<span class="ft-ic">${S.icon(it.icon)}</span><span class="ft-t"><b>${esc(it.name)}</b><small>${esc(it.desc)}</small></span>${it.built ? '' : '<span class="ft-demo">示範頁</span>'}`;
    return it.action ? `<button type="button" class="ft" data-act="${it.action}">${inner}</button>` : `<a class="ft" href="${esc(it.route)}">${inner}</a>`;
  }
  function renderTiles(q) {
    const terms = String(q || '').trim().toLowerCase().split(/\s+/).filter(Boolean);
    const match = (it, cat) => terms.every((t) => [cat, it.name, it.desc, (it.kw || []).join(' '), (it.subs || []).join(' ')].join(' ').toLowerCase().indexOf(t) >= 0);
    let n = 0;
    const html = DS.getFeatures().map((g) => {
      const items = g.items.filter((it) => match(it, g.cat)); n += items.length;
      return items.length ? `<section class="fgroup"><h2>${esc(g.cat)}</h2><div class="ftiles">${items.map(tile).join('')}</div></section>` : '';
    }).join('');
    return n ? html : `<div class="empty">找不到「${esc(q)}」。<br><button class="btn btn-sm btn-primary" type="button" data-act="open-asla" data-q="${esc(q)}">問問阿斯拉</button></div>`;
  }
  S.views.more = {
    tab: 'more', title: '全部功能',
    render(p) {
      return `<div class="page-head"><div><h1>全部功能</h1><p class="muted small">全部都在站內完成，不用跳到其他系統</p></div></div>
        <div class="searchbar">${S.icon('search')}<input id="more-q" type="search" placeholder="找功能：就貸、宿舍、請假、期中退選…" value="${esc(p.get('q') || '')}" aria-label="搜尋功能"></div>
        <div id="ftiles">${renderTiles(p.get('q'))}</div>`;
    },
    after() { const i = S.$('#more-q'); i.addEventListener('input', () => { S.$('#ftiles').innerHTML = renderTiles(i.value); }); }
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
    title: (sub) => (DS.getFeature(sub) || { name: '功能' }).name,
    render(p, sub) {
      const f = DS.getFeature(sub);
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
