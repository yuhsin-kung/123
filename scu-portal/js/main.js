/* =========================================================================
 * main.js — 啟動程式（最後載入）
 * -------------------------------------------------------------------------
 * 1. SCU.DS.init()：資料存取層載入資料（現為本機示範資料；之後可換成後端 API）
 * 2. 讀取本機使用者資料（課表、選課車…）
 * 3. 網址示範參數：
 *      ?demo=conflict   載入「衝堂＋額滿＋學分超過」的示範選課車並打開選課車
 *      ?demo=reset      清除本機資料，恢復初始示範課表
 *      ?asla=問題        打開阿斯拉並直接提問（可重複多個 asla 參數）
 *    （日期時間參數 ?date=&time= 在 config.js 處理）
 * 4. 頁首顯示登入學生、渲染目前頁面
 * ========================================================================= */
(function () {
  'use strict';
  const S = window.SCU;

  S.loadConflictDemo = function () {
    /* DS301 機器學習（週三 7–9）與課表中的 DS303 衝堂；DS305 深度學習專題已額滿且與週四體育、通識衝堂；總學分超過 25 */
    S.state.cart = { add: ['DS301', 'DS305'], drop: [] }; S.save();
  };

  S.DS.init().then(() => {
    S.initState();
    const q = new URLSearchParams(location.search);
    const demo = q.get('demo');
    if (demo === 'reset') S.resetDemo();
    if (demo === 'conflict') { S.loadConflictDemo(); if (!location.hash || location.hash === '#') history.replaceState(null, '', location.pathname + location.search + '#/course?tab=cart'); }

    const P = S.DS.getProfile();
    S.$('#who').innerHTML = `<b>${S.esc(P.name)}</b><span>${S.esc(P.program)}・${S.esc(P.dept)} ${P.grade}${S.esc(P.cls)}</span>`;
    S.$('#who').title = `${P.name}（${P.studentId}）${P.program} ${P.dept} ${P.grade} 年級 ${P.cls} 班`;

    S.render();
    const asks = q.getAll('asla');
    if (asks.length && S.openAsla) { S.openAsla(); asks.forEach(S.askAsla); }
  }).catch((err) => {
    S.$('#view').innerHTML = `<div class="empty">資料載入失敗：${S.esc(err && err.message)}</div>`;
  });
})();
