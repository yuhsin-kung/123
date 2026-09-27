/* =========================================================================
 * pages/grades.js — 成績（#/grades）
 * -------------------------------------------------------------------------
 * gradeSummary()：依 data-grades.js 計算每學期「加權平均、GPA（4.3 制示範換算）、
 *                 修習／實得學分」與累計數字（首頁捷徑與阿斯拉也會用）。
 * 畫面：累計摘要（GPA、平均、實得學分、最近系排）→ 畢業學分進度（#grad）→
 *       各學期 GPA 趨勢 → 所有學期成績卡（新到舊，全部同時展開）→ 本學期修課中。
 * ========================================================================= */
(function () {
  'use strict';
  const S = window.SCU; const esc = S.esc; const DS = S.DS;

  function letter(score) { return DS.getGpaScale().find((g) => score >= g.min); }
  S.gradeLetter = letter;

  S.gradeSummary = function () {
    const sems = DS.getGrades().map((g) => {
      let att = 0, earned = 0, wsum = 0, gsum = 0;
      g.courses.forEach(([, cr, sc]) => { att += cr; wsum += cr * sc; gsum += cr * letter(sc).gp; if (sc >= 60) earned += cr; });
      return Object.assign({}, g, { attempted: att, earned, avg: wsum / att, gpa: gsum / att, pct: g.deptRank[0] / g.deptRank[1] * 100 });
    });
    const att = sems.reduce((a, s) => a + s.attempted, 0);
    const cum = {
      attempted: att,
      earned: sems.reduce((a, s) => a + s.earned, 0),
      avg: sems.reduce((a, s) => a + s.avg * s.attempted, 0) / att,
      gpa: sems.reduce((a, s) => a + s.gpa * s.attempted, 0) / att
    };
    return { sems, cum, latest: sems[sems.length - 1] };
  };

  function semCard(s) {
    return `<article class="card sem">
      <div class="sem-head"><div><h3>${s.sem}</h3><span class="small muted">${esc(s.label)}</span></div><div class="sem-gpa"><b>${s.gpa.toFixed(2)}</b><small>GPA</small></div></div>
      <div class="sem-metrics">
        <div><small>平均</small><b>${s.avg.toFixed(1)}</b></div>
        <div><small>班排</small><b>${s.classRank[0]}<span>/${s.classRank[1]}</span></b></div>
        <div><small>系排</small><b>${s.deptRank[0]}<span>/${s.deptRank[1]}</span></b></div>
        <div><small>系排百分比</small><b>前 ${s.pct.toFixed(1)}%</b></div>
        <div><small>操行</small><b>${s.conduct}</b></div>
        <div><small>實得學分</small><b>${s.earned}<span>/${s.attempted}</span></b></div>
      </div>
      <table class="gtable"><thead><tr><th>科目</th><th>類別</th><th>學分</th><th>分數</th><th>等第</th></tr></thead><tbody>
        ${s.courses.map(([n, cr, sc, t]) => { const L = letter(sc); return `<tr class="${sc < 60 ? 'fail' : ''}"><td>${esc(n)}${sc < 60 ? ' <span class="pill-mini bad">未通過</span>' : ''}</td><td><span class="type type-${t}">${t}</span></td><td>${cr}</td><td><b>${sc}</b></td><td>${L.letter}</td></tr>`; }).join('')}
      </tbody></table></article>`;
  }

  S.views.grades = {
    tab: 'grades', title: '成績',
    render() {
      const P = DS.getProfile();
      if (P.role === 'teacher') {
        return `<div class="page-head"><div><h1>成績</h1><p class="muted small">教師帳號沒有個人成績單</p></div></div>
          <section class="card"><p>成績是學生功能。請登出後用學號登入。</p></section>`;
      }
      const G = S.gradeSummary(); const need = DS.getGradCredits();
      const cur = S.myCourses(); const curCr = S.sumCredits(cur);
      const pctDone = G.cum.earned / need * 100, pctCur = Math.min(100 - pctDone, curCr / need * 100);
      const maxGpa = 4.3;
      return `
      <div class="page-head"><div><h1>成績</h1><p class="muted small">所有學期一次看・${esc(DS.getProfile().name)}（${esc(DS.getProfile().studentId)}）</p></div></div>
      <section class="metrics">
        <div class="metric hi"><small>累計 GPA</small><b>${G.cum.gpa.toFixed(2)}</b><span>／4.3</span></div>
        <div class="metric"><small>累計平均</small><b>${G.cum.avg.toFixed(1)}</b><span>分</span></div>
        <div class="metric"><small>實得學分</small><b>${G.cum.earned}</b><span>／修習 ${G.cum.attempted}</span></div>
        <div class="metric"><small>最近系排（${G.latest.sem}）</small><b>${G.latest.deptRank[0]}</b><span>／${G.latest.deptRank[1]}・前 ${G.latest.pct.toFixed(1)}%</span></div>
      </section>

      <section class="card section" id="grad">
        <div class="sec-head"><h2>${S.icon('cap')}畢業學分進度</h2><span class="small muted">門檻 ${need} 學分（示範）</span></div>
        <div class="bar2"><i class="done" style="width:${pctDone}%"></i><i class="cur" style="width:${pctCur}%"></i></div>
        <p class="small">已實得 <b>${G.cum.earned}</b> 學分・本學期修課中 <b>${curCr}</b> 學分・全部通過後還差 <b>${Math.max(0, need - G.cum.earned - curCr)}</b> 學分</p>
      </section>

      <section class="card section">
        <div class="sec-head"><h2>各學期 GPA</h2><span class="tiny muted">長條由 2.0 起算</span></div>
        <div class="trend">${G.sems.map((s) => `<div class="trend-col"><span class="trend-v">${s.gpa.toFixed(2)}</span><div class="trend-bar"><i style="height:${Math.max(6, (s.gpa - 2) / (maxGpa - 2) * 100)}%"></i></div><small>${s.sem}</small></div>`).join('')}</div>
      </section>

      <section class="section"><div class="sec-head"><h2>所有學期成績</h2><span class="tiny muted">GPA 依示範換算表（A+ 4.3 … F 0）</span></div>
        <div class="sem-grid">
          <article class="card sem sem-current"><div class="sem-head"><div><h3>${S.SEMESTER.code}</h3><span class="small muted">本學期・修課中</span></div><span class="pill-mini">成績尚未公布</span></div>
            <p class="small muted">${cur.length} 門、${curCr} 學分，期末考週後公布（示範）。</p>
            <div class="chips">${cur.map((c) => `<span class="chip">${esc(c.name)}</span>`).join('')}</div></article>
          ${G.sems.slice().reverse().map(semCard).join('')}
        </div></section>`;
    },
    after(p) { if (p.get('focus') === 'grad') setTimeout(() => S.$('#grad').scrollIntoView({ block: 'center' }), 50); }
  };
})();
