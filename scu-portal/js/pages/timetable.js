/* =========================================================================
 * pages/timetable.js — 我的課表（#/timetable）
 * -------------------------------------------------------------------------
 * 區塊一 我的課表：週一～五 × 第 1–10 節格線，每門課顯示課名、教室、剩餘名額；
 *                 上方顯示總學分與課程數，今天那一欄會標示「今天」。
 * 區塊二 課程清單：依星期排列，含時間、老師、學分、剩餘名額。
 * 區塊三 查班級課表：學制／系所／年級／班別 下拉選單，預設帶入登入學生（profile.js），
 *                   可自行更改；資料經 data-source.js 的 getClassTimetable() 取得。
 * ========================================================================= */
(function () {
  'use strict';
  const S = window.SCU; const esc = S.esc; const DS = S.DS;

  function courseList(list) {
    const rows = [];
    for (let d = 1; d <= 5; d++) {
      list.forEach((c) => c.slots.filter((s) => s.day === d).forEach((s) => rows.push({ c, s, d })));
    }
    rows.sort((a, b) => a.d - b.d || a.s.start - b.s.start);
    return rows.map((x) => `<div class="crow">
      <div class="crow-day"><b>週${S.WD[x.d]}</b><small>${S.slotRange(x.s)}</small></div>
      <div class="crow-main"><b>${esc(x.c.name)}</b> ${S.typeTag(x.c)}<br><span class="small muted">${esc(x.c.teacher)}・${esc(x.s.room || x.c.room)}${x.s.week ? '・' + x.s.week + '週' : ''}・${x.c.credits} 學分</span></div>
      <div class="crow-side">${S.remainBadge(x.c)}</div></div>`).join('');
  }

  function todayDay() { const wd = S.weekday(S.today); return wd >= 1 && wd <= 5 ? wd : 0; }

  S.views.timetable = {
    tab: 'timetable', title: '我的課表',
    render(params) {
      const list = S.myCourses(); const P = DS.getProfile(); const O = DS.getClassOptions();
      const w = S.state.withdrawn.map(DS.getCourse).filter(Boolean);
      const opt = (arr, v, fmt) => arr.map((x) => `<option value="${esc(x)}" ${String(x) === String(v) ? 'selected' : ''}>${esc(fmt ? fmt(x) : x)}</option>`).join('');
      const q = { program: params.get('program') || P.program, dept: params.get('dept') || P.dept, grade: params.get('grade') || P.grade, cls: params.get('cls') || P.cls };
      return `
      ${params.get('submitted') ? `<div class="notice good">${S.icon('check')}已送出，課表已更新（示範：只存在這台電腦的瀏覽器）。</div>` : ''}
      <div class="page-head"><div><h1>我的課表</h1><p class="muted small">${S.SEMESTER.label}・${esc(P.dept)} ${P.grade} 年級 ${esc(P.cls)} 班</p></div>
        <a class="btn btn-primary btn-sm" href="#/course">${S.icon('course')}調整課表（選課）</a></div>
      <div class="stats">
        <div class="stat"><small>總學分</small><b>${S.sumCredits(list)}</b></div>
        <div class="stat"><small>課程數</small><b>${list.length}</b></div>
        <div class="stat"><small>本週</small><b>${S.semesterWeek() ? '第 ' + S.semesterWeek() + ' 週' : '—'}</b></div>
      </div>
      <section class="card flush">${S.mobileWeek(list)}<div class="only-desk">${S.timetableSheet(list)}</div></section>
      ${w.length ? `<div class="notice">期中退選（W）：${w.map((c) => esc(c.name)).join('、')}</div>` : ''}
      <section class="section"><div class="sec-head"><h2>課程清單</h2></div><div class="card flush clist">${list.length ? courseList(list) : '<div class="empty">課表是空的，去「選課」加幾門課吧。</div>'}</div></section>

      <section class="section" id="class-query">
        <div class="sec-head"><h2>${S.icon('search')}查班級課表</h2><span class="tiny muted">預設帶入你的班級，可自行更改</span></div>
        <form class="card filters" id="cq-form">
          <label>學制<select name="program">${opt(O.programs, q.program)}</select></label>
          <label>系所<select name="dept">${opt(O.depts, q.dept)}</select></label>
          <label>年級<select name="grade">${opt(O.grades, q.grade, (g) => g + ' 年級')}</select></label>
          <label>班別<select name="cls">${opt(O.classes, q.cls, (k) => k + ' 班')}</select></label>
          <button class="btn btn-sm" type="button" data-act="cq-mine">回到我的班級</button>
        </form>
        <div id="cq-result"></div>
      </section>`;
    },
    after(params) {
      const f = S.$('#cq-form');
      const run = () => {
        const program = f.program.value, dept = f.dept.value, grade = +f.grade.value, cls = f.cls.value;
        const box = S.$('#cq-result'); box.innerHTML = '<div class="empty">查詢中…</div>';
        DS.getClassTimetable(program, dept, grade, cls).then((res) => {
          const list = S.coursesOf(res.codes);
          const P = DS.getProfile();
          const mine = program === P.program && dept === P.dept && grade === +P.grade && cls === P.cls;
          box.innerHTML = list.length ? `<p class="small"><b>${esc(program)}・${esc(dept)} ${grade} 年級 ${esc(cls)} 班</b>${mine ? '<span class="pill-mini">你的班級</span>' : ''}：${list.length} 門、${S.sumCredits(list)} 學分（示範資料）</p>
            <div class="card flush">${S.timetableSheet(list)}</div>
            <div class="card flush clist" style="margin-top:10px">${courseList(list)}</div>`
            : `<div class="empty">${esc(res.note || '查無資料')}</div>`;
        });
      };
      f.addEventListener('change', run);
      run();
      if (params.get('focus') === 'class') setTimeout(() => S.$('#class-query').scrollIntoView({ block: 'start' }), 50);
    }
  };
  S.actions['cq-mine'] = () => {
    const f = S.$('#cq-form'); const P = DS.getProfile();
    f.program.value = P.program; f.dept.value = P.dept; f.grade.value = String(P.grade); f.cls.value = P.cls;
    f.dispatchEvent(new Event('change'));
  };
})();
