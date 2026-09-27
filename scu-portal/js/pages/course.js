/* =========================================================================
 * pages/course.js — 選課（#/course）
 * -------------------------------------------------------------------------
 * 分頁「時段找課」(#/course?tab=find)：選星期＋節次起訖（可加關鍵字、類別、只看有名額、
 *     只看不衝堂），列出該時段所有課；可「加選」到選課車，或把已在課表的課「退選」。
 * 分頁「選課車」(#/course?tab=cart)：
 *     1. 異動清單（待加選／待退選）
 *     2. 送出前檢查（S.runChecks，寫在 core.js）：衝堂、學分 16–25（示範規則）、額滿，
 *        有問題時列出原因並推薦替代課程（一鍵替換／加入）
 *     3. 送出後課表預覽（衝堂紅框、新加選虛線框）
 *     4. 「送出」：檢查全部通過才可按；只把結果存回本機課表（不連接學校系統）
 * ========================================================================= */
(function () {
  'use strict';
  const S = window.SCU; const esc = S.esc; const DS = S.DS; const st = S.state;

  /* 選課期間提示（取自行事曆 type=course） */
  function periodBanner() {
    const evs = DS.getEvents().filter((e) => e.type === 'course' && S.eventEnd(e) >= S.today);
    const on = evs.find((e) => e.start <= S.today);
    if (on) { const cd = S.countdown(on); return `<div class="notice ${cd.urgent ? 'warn' : 'good'}">${S.icon('clock')}<span><b>${esc(on.title)}進行中</b>（${S.eventRange(on)}）・${cd.label}</span></div>`; }
    if (evs[0]) { const cd = S.countdown(evs[0]); return `<div class="notice">${S.icon('calendar')}<span>下一個選課時段：<b>${esc(evs[0].title)}</b> ${S.eventRange(evs[0])}（${cd.label}）。示範模式下仍可操作。</span></div>`; }
    return '';
  }

  function tabs(tab) {
    return `<div class="seg" role="tablist">
      <a role="tab" href="#/course?tab=find" class="${tab === 'find' ? 'on' : ''}" aria-selected="${tab === 'find'}">${S.icon('search')}時段找課</a>
      <a role="tab" href="#/course?tab=cart" class="${tab === 'cart' ? 'on' : ''}" aria-selected="${tab === 'cart'}">${S.icon('cart')}選課車<span class="cart-badge" hidden></span></a></div>`;
  }

  /* ---------------- 時段找課 ---------------- */
  function findForm(p) {
    const day = +(p.get('day') || 3), from = +(p.get('from') || 6), to = +(p.get('to') || 9);
    const last = DS.getPeriods().length;
    const pOpt = (v) => DS.getPeriods().map((x) => `<option value="${x.p}" ${v === x.p ? 'selected' : ''}>第 ${x.label || x.p} 節 ${x.t.split('–')[0]}</option>`).join('');
    return `<form id="find-form" class="card filters find-form" autocomplete="off">
      <div class="daypick" role="radiogroup" aria-label="星期">${[1, 2, 3, 4, 5].map((d) => `<label><input type="radio" name="day" value="${d}" ${d === day ? 'checked' : ''}><span>週${S.WD[d]}</span></label>`).join('')}</div>
      <label>從<select name="from">${pOpt(from)}</select></label>
      <label>到<select name="to">${pOpt(to)}</select></label>
      <div class="quick">${[['上午', 1, 4], ['中午', 5, 5], ['下午', 6, 10], ['晚上', 11, last], ['整天', 1, last]].map((q) => `<button type="button" class="chip-btn" data-act="find-range" data-from="${q[1]}" data-to="${q[2]}">${q[0]}</button>`).join('')}</div>
      <label class="grow">關鍵字<input name="q" type="search" placeholder="課名、老師、代碼" value="${esc(p.get('q') || '')}"></label>
      <label>類別<select name="type"><option value="">全部</option>${['必修', '選修', '通識'].map((t) => `<option ${p.get('type') === t ? 'selected' : ''}>${t}</option>`).join('')}</select></label>
      <label class="inline"><input type="checkbox" name="avail" ${p.get('avail') ? 'checked' : ''}> 只看有名額</label>
      <label class="inline"><input type="checkbox" name="free" ${p.get('free') ? 'checked' : ''}> 只看不衝堂</label>
    </form>`;
  }
  function courseCard(c, planned, myDept) {
    const inT = S.inTimetable(c.code), add = S.inCartAdd(c.code), drop = S.inCartDrop(c.code);
    const cf = drop ? [] : S.conflictsWith(c, planned); /* 與送出後課表中其他課衝堂 */
    let btn, state = '';
    if (inT && !drop) { state = '<span class="pill-mini ok">已在課表</span>'; btn = `<button class="btn btn-sm" type="button" data-act="cart-drop" data-code="${c.code}">退選</button>`; }
    else if (inT && drop) { state = '<span class="pill-mini bad">待退選</span>'; btn = `<button class="btn btn-sm" type="button" data-act="cart-undrop" data-code="${c.code}">取消退選</button>`; }
    else if (add) { state = '<span class="pill-mini new">已加入選課車</span>'; btn = `<button class="btn btn-sm" type="button" data-act="cart-unadd" data-code="${c.code}">移出</button>`; }
    else btn = `<button class="btn btn-sm btn-primary" type="button" data-act="cart-add" data-code="${c.code}">${S.icon('plus')}加選</button>`;
    return `<article class="ccard ${inT && !drop ? 'is-mine' : ''} ${add ? 'is-add' : ''}">
      <div class="ccard-top"><span class="code">${c.code}</span>${S.typeTag(c)}${c.dept === myDept ? '<span class="pill-mini">本系</span>' : ''}${state}</div>
      <h3>${esc(c.name)}</h3>
      <p class="small muted">${esc(c.teacher)}・${esc(c.dept)}・${c.credits} 學分</p>
      <p class="small">${S.slotText(c)}（${c.slots.map(S.slotRange).join('、')}）・${esc(c.room)}</p>
      <div class="ccard-foot">${S.remainBadge(c)}<span class="grow"></span>${btn}</div>
      ${cf.length ? `<p class="warn-line">${S.icon('alert')}與「${esc(cf[0].name)}」衝堂</p>` : ''}
      ${!inT && !add && S.remain(c) <= 0 ? `<p class="warn-line">${S.icon('alert')}已額滿，送出前檢查會建議替代課程</p>` : ''}
    </article>`;
  }
  function runFind() {
    const f = S.$('#find-form'); if (!f) return;
    const day = +f.day.value; let from = +f.from.value, to = +f.to.value;
    if (from > to) { const t = from; from = to; to = t; }
    const q = f.q.value.trim().toLowerCase(), type = f.type.value, avail = f.avail.checked, free = f.free.checked;
    const planned = S.plannedCourses(); const myDept = DS.getProfile().dept;
    const sortC = (a, b) => (b.dept === myDept) - (a.dept === myDept) || a.slots[0].start - b.slots[0].start || a.code.localeCompare(b.code);
    const textOf = (c) => [c.code, c.name, c.teacher, c.dept].join(' ').toLowerCase();
    const pass = (c, inSlot) => {
      if (type && c.type !== type) return false;
      if (avail && S.remain(c) <= 0) return false;
      if (q && textOf(c).indexOf(q) < 0) return false;
      if (!q && !inSlot) return false;
      if (free && !S.inTimetable(c.code) && S.conflictsWith(c, planned).length) return false;
      return true;
    };
    const inSlot = (c) => c.slots.some((s) => s.day === day && s.start <= to && s.end >= from);
    const all = DS.getCourses().filter((c) => c.slots.length);
    const list = all.filter((c) => inSlot(c) && pass(c, true)).sort(sortC);
    const others = q ? all.filter((c) => !inSlot(c) && pass(c, false)).sort(sortC) : [];
    /* 同步網址（方便分享／重新整理），不觸發重新渲染 */
    const qs = new URLSearchParams({ tab: 'find', day, from, to });
    if (q) qs.set('q', f.q.value.trim()); if (type) qs.set('type', type); if (avail) qs.set('avail', 1); if (free) qs.set('free', 1);
    history.replaceState(null, '', '#/course?' + qs.toString());
    const slotHead = `週${S.WD[day]} 第 ${from}${to > from ? '–' + to : ''} 節（${S.periodStart(from)}–${S.periodEnd(to)}）：<b>${list.length}</b> 門課`;
    const slotBody = list.length
      ? `<div class="ccards">${list.map((c) => courseCard(c, planned, myDept)).join('')}</div>`
      : '<div class="empty">這個時段沒有符合條件的課。</div>';
    const otherBody = others.length
      ? `<p class="result-head">其他時段也符合「${esc(f.q.value.trim())}」：<b>${others.length}</b> 門</p><div class="ccards">${others.map((c) => courseCard(c, planned, myDept)).join('')}</div>`
      : '';
    S.$('#find-result').innerHTML = `<p class="result-head">${slotHead}</p>${slotBody}${otherBody}`;
    cartBar();
  }
  function cartBar() {
    const b = S.$('#cartbar'); if (!b) return;
    const n = S.cartCount(); const r = S.runChecks();
    b.innerHTML = n ? `<div class="cartbar"><span>${S.icon('cart')}選課車 <b>${n}</b> 項・送出後 <b>${r.credits}</b> 學分${r.ok ? '' : '<span class="pill-mini bad">有問題待處理</span>'}</span>
      <a class="btn btn-sm btn-primary" href="#/course?tab=cart">檢查並送出 ${S.icon('right')}</a></div>` : '';
  }

  /* ---------------- 選課車＋送出前檢查 ---------------- */
  function altRow(c, act, old, label) {
    return `<div class="alt"><div><span class="code">${c.code}</span> <b>${esc(c.name)}</b> ${S.typeTag(c)}<br><span class="small muted">${S.slotText(c)}・${esc(c.dept)}・${c.credits} 學分</span> ${S.remainBadge(c)}</div>
      <button class="btn btn-sm btn-primary" type="button" data-act="${act}" data-code="${c.code}" ${old ? `data-old="${old}"` : ''}>${label}</button></div>`;
  }
  function cartView() {
    const adds = S.coursesOf(st.cart.add), drops = S.coursesOf(st.cart.drop);
    const r = S.runChecks(); const rule = DS.getCreditRule();
    const nowCredits = S.sumCredits(S.myCourses());
    if (!adds.length && !drops.length) {
      return `<div class="empty big">${S.icon('cart', 'ic-lg')}<b>選課車是空的</b><p>到「時段找課」加選，或把課表裡的課退選。</p><a class="btn btn-primary" href="#/course?tab=find">去時段找課</a></div>
        <section class="section"><div class="sec-head"><h2>目前課表</h2><span class="small muted">${nowCredits} 學分</span></div><div class="card flush">${S.timetableGrid(S.myCourses(), {})}</div></section>`;
    }
    const row = (c, kind) => `<div class="crow ${kind === 'add' && r.conflictCodes.has(c.code) ? 'is-conflict' : ''}">
      <span class="op op-${kind}">${kind === 'add' ? '加選' : '退選'}</span>
      <div class="crow-main"><b>${esc(c.name)}</b> <span class="code">${c.code}</span><br><span class="small muted">${S.slotText(c)}・${c.credits} 學分・${esc(c.teacher)}</span></div>
      <div class="crow-side">${kind === 'add' ? S.remainBadge(c) : ''}<button class="btn btn-sm" type="button" data-act="${kind === 'add' ? 'cart-unadd' : 'cart-undrop'}" data-code="${c.code}">${kind === 'add' ? '移出' : '取消'}</button></div></div>`;

    /* 檢查結果與替代建議 */
    const issues = []; const handled = new Set();
    r.conflicts.forEach((x) => {
      const where = x.ov.map((o) => `週${S.WD[o.day]} 第 ${o.from}${o.to > o.from ? '–' + o.to : ''} 節`).join('、');
      const target = S.inCartAdd(x.b.code) && !S.inTimetable(x.b.code) ? x.b : x.a; /* 建議替換新加選的那門 */
      let alt = '';
      if (!handled.has(target.code)) { handled.add(target.code); const alts = S.alternativesFor(target, r.planned, 3);
        alt = `<div class="alt-for">「${esc(target.name)}」可改選（有名額、不衝堂）：</div><div class="alts">${alts.length ? alts.map((a) => altRow(a, 'swap', target.code, '替換')).join('') : '<p class="small muted">找不到合適的替代課程。</p>'}</div>`; }
      issues.push(`<li><b>衝堂</b>：「${esc(x.a.name)}」與「${esc(x.b.name)}」在 ${where} 時間重疊。${alt}</li>`);
    });
    r.full.forEach((c) => {
      let alt = '';
      if (!handled.has(c.code)) { handled.add(c.code); const alts = S.alternativesFor(c, r.planned, 3);
        alt = `<div class="alt-for">「${esc(c.name)}」可改選：</div><div class="alts">${alts.length ? alts.map((a) => altRow(a, 'swap', c.code, '替換')).join('') : '<p class="small muted">找不到合適的替代課程。</p>'}</div>`; }
      issues.push(`<li><b>額滿</b>：「${esc(c.name)}」剩餘名額 0/${c.cap}，無法加選。${alt}</li>`);
    });
    if (r.creditIssue === 'low') {
      const sug = S.fillSuggestions(r.planned, 4);
      issues.push(`<li><b>學分不足</b>：送出後 ${r.credits} 學分，低於下限 ${rule.min} 學分（還差 ${rule.min - r.credits}）。<div class="alt-for">可補進空堂、且有名額的課：</div><div class="alts">${sug.map((a) => altRow(a, 'cart-add', '', '加選')).join('')}</div></li>`);
    }
    if (r.creditIssue === 'high') {
      const removable = adds.slice().sort((a, b) => (a.type === '必修') - (b.type === '必修')); /* 選修／通識優先建議移出 */
      issues.push(`<li><b>學分超過上限</b>：送出後 ${r.credits} 學分，高於上限 ${rule.max} 學分（多 ${r.credits - rule.max}）。建議移出部分課程${removable.length ? '：' + removable.map((c) => `<button class="btn btn-sm" type="button" data-act="cart-unadd" data-code="${c.code}">移出 ${esc(c.name)}</button>`).join(' ') : '。'}</li>`);
    }
    const checkLine = (ok, label, detail) => `<li class="${ok ? 'ok' : 'bad'}">${S.icon(ok ? 'check' : 'x')}<b>${label}</b><span>${detail}</span></li>`;
    const newCodes = new Set(adds.map((c) => c.code));
    return `
    <section class="card"><div class="sec-head"><h2>異動清單</h2><button class="btn btn-sm btn-ghost" type="button" data-act="cart-clear">清空</button></div>
      <div class="clist">${adds.map((c) => row(c, 'add')).join('')}${drops.map((c) => row(c, 'drop')).join('')}</div></section>

    <section class="card section check ${r.ok ? 'is-ok' : 'is-bad'}" id="check">
      <div class="sec-head"><h2>送出前檢查</h2><span class="pill-mini ${r.ok ? 'ok' : 'bad'}">${r.ok ? '全部通過' : `${issues.length} 個問題`}</span></div>
      <ul class="checks">
        ${checkLine(!r.conflicts.length, '衝堂', r.conflicts.length ? `${r.conflicts.length} 組衝堂` : '沒有衝堂')}
        ${checkLine(!r.creditIssue, '學分', `目前 ${nowCredits} → 送出後 <b>${r.credits}</b> 學分（示範規則 ${rule.min}–${rule.max}）`)}
        ${checkLine(!r.full.length, '名額', r.full.length ? `${r.full.length} 門已額滿` : '加選的課都有名額')}
      </ul>
      ${issues.length ? `<ol class="issues">${issues.join('')}</ol>` : ''}
    </section>

    <section class="section"><div class="sec-head"><h2>送出後的課表預覽</h2><span class="tiny muted"><i class="lg lg-new"></i>新加選 <i class="lg lg-bad"></i>衝堂</span></div>
      <div class="card flush">${S.timetableGrid(r.planned, { conflictCodes: r.conflictCodes, newCodes })}</div></section>

    <div class="submit-bar">
      <div><b>${r.ok ? '可以送出了' : '修正上面的問題後才能送出'}</b><br><span class="tiny muted">送出只會更新這台電腦上的示範課表，不會連到學校系統。</span></div>
      <button class="btn btn-primary btn-lg" type="button" data-act="cart-submit" ${r.ok ? '' : 'disabled'}>送出</button>
    </div>`;
  }

  S.views.course = {
    tab: 'course', title: '選課',
    render(p) {
      const tab = p.get('tab') === 'cart' ? 'cart' : 'find';
      if (DS.getProfile().role === 'teacher') {
        return `<div class="page-head"><div><h1>選課</h1><p class="muted small">教師帳號不能加退選</p></div></div>
          <section class="card"><p>加退選是學生功能。你的開課在「我的課表」。</p>
          <p><a class="btn btn-primary btn-sm" href="#/timetable">看我的開課</a></p></section>`;
      }
      return `<div class="page-head"><div><h1>選課</h1><p class="muted small">${S.SEMESTER.label}・學分規則 ${DS.getCreditRule().min}–${DS.getCreditRule().max}（示範）</p></div></div>
        ${periodBanner()}${tabs(tab)}
        ${tab === 'find' ? `${findForm(p)}<div id="find-result"></div><div id="cartbar"></div>` : `<div id="cart-view">${cartView()}</div>`}`;
    },
    after(p) {
      if (DS.getProfile().role === 'teacher') return;
      if (p.get('tab') === 'cart') return;
      const f = S.$('#find-form');
      f.addEventListener('change', runFind);
      f.q.addEventListener('input', runFind);
      f.addEventListener('submit', (e) => { e.preventDefault(); runFind(); });
      runFind();
    }
  };

  /* ---------------- 動作 ---------------- */
  function afterChange() {
    S.save(); S.updateBadges();
    if (S.$('#find-form')) runFind();
    else if (S.$('#cart-view')) S.$('#cart-view').innerHTML = cartView();
  }
  const A = S.actions;
  A['cart-add'] = (t) => { const c = t.dataset.code; if (!S.inCartAdd(c) && !S.inTimetable(c)) st.cart.add.push(c); if (S.inCartDrop(c)) st.cart.drop = st.cart.drop.filter((x) => x !== c); S.toast('已加入選課車：' + DS.getCourse(c).name); afterChange(); };
  A['cart-unadd'] = (t) => { st.cart.add = st.cart.add.filter((x) => x !== t.dataset.code); afterChange(); };
  A['cart-drop'] = (t) => { const c = t.dataset.code; if (!S.inCartDrop(c)) st.cart.drop.push(c); S.toast('已加入待退選：' + DS.getCourse(c).name); afterChange(); };
  A['cart-undrop'] = (t) => { st.cart.drop = st.cart.drop.filter((x) => x !== t.dataset.code); afterChange(); };
  A['cart-clear'] = () => { if (confirm('清空選課車？')) { st.cart = { add: [], drop: [] }; afterChange(); } };
  A['swap'] = (t) => {
    const old = t.dataset.old, code = t.dataset.code;
    if (S.inCartAdd(old)) st.cart.add[st.cart.add.indexOf(old)] = code;
    else { if (S.inTimetable(old) && !S.inCartDrop(old)) st.cart.drop.push(old); st.cart.add.push(code); }
    S.toast(`已將「${DS.getCourse(old).name}」換成「${DS.getCourse(code).name}」`); afterChange();
  };
  A['find-range'] = (t) => { const f = S.$('#find-form'); f.from.value = t.dataset.from; f.to.value = t.dataset.to; runFind(); };
  A['cart-submit'] = () => {
    const r = S.runChecks(); if (!r.ok) return;
    st.cart.add.forEach((c) => { if (!S.inTimetable(c)) st.seatDelta[c] = (st.seatDelta[c] || 0) + 1; });
    st.cart.drop.forEach((c) => { st.seatDelta[c] = (st.seatDelta[c] || 0) - 1; });
    st.timetable = S.plannedCodes(); st.cart = { add: [], drop: [] };
    S.save(); S.toast('已送出，課表已更新');
    S.go('#/timetable?submitted=1');
  };
})();
