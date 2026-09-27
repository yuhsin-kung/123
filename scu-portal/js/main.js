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

    function paintWho() {
      const P = S.DS.getProfile();
      const who = S.$('#who');
      const out = S.$('#logout');
      if (!P || !S.readLogin()) {
        who.href = '#/login';
        who.innerHTML = '<b>登入</b>';
        who.title = '學生或教師登入';
        if (out) out.hidden = true;
        return;
      }
      who.href = '#/p/profile';
      if (P.role === 'teacher') {
        who.innerHTML = `<b>${S.esc(P.name)}</b><span>教師・${S.esc(P.dept)}</span>`;
        who.title = `${P.name}（${P.staffId}）教師`;
      } else {
        who.innerHTML = `<b>${S.esc(P.name)}</b><span>學生・${S.esc(P.dept)} ${P.grade}${S.esc(P.cls)}</span>`;
        who.title = `${P.name}（${P.studentId}）學生`;
      }
      if (out) out.hidden = false;
    }
    function showLogin() {
      paintWho();
      document.body.classList.add('login-mode');
      S.$('#view').innerHTML = `
        <form class="card login-card" id="login-form" data-role="student">
          <img class="login-logo" src="img/scu-logo.png" alt="">
          <h1>東吳學生新入口</h1>
          <p class="muted small login-lead">選擇身分後登入</p>
          <div class="login-switch" role="tablist">
            <button type="button" class="on" data-role="student">學生</button>
            <button type="button" data-role="teacher">教師</button>
          </div>
          <p class="small muted" id="login-hint">使用學號登入。示範學號 11316025，密碼 demo1234。</p>
          <label><span id="login-id-name">學號</span><input name="id" autocomplete="username" required></label>
          <label>密碼<input name="password" type="password" autocomplete="current-password" required></label>
          <p class="login-err" hidden>帳號或密碼不對。學生請用學號，教師請用教職員帳號。</p>
          <button class="btn btn-primary" type="submit" id="login-submit">登入</button>
        </form>`;
      const form = S.$('#login-form');
      const hint = S.$('#login-hint');
      const idName = S.$('#login-id-name');
      const setRole = (role) => {
        form.dataset.role = role;
        form.querySelector('.login-err').hidden = true;
        S.$$('.login-switch button').forEach((b) => b.classList.toggle('on', b.dataset.role === role));
        const teacher = role === 'teacher';
        idName.textContent = teacher ? '教職員帳號' : '學號';
        hint.textContent = teacher
          ? '使用教職員帳號登入。示範帳號 T2019001，密碼 demo1234。'
          : '使用學號登入。示範學號 11316025，密碼 demo1234。';
      };
      S.$('.login-switch').addEventListener('click', (e) => {
        const b = e.target.closest('[data-role]');
        if (b) setRole(b.dataset.role);
      });
      form.addEventListener('submit', (e) => {
        e.preventDefault();
        const role = form.dataset.role === 'teacher' ? 'teacher' : 'student';
        const id = form.id.value.trim();
        const password = form.password.value;
        const acc = role === 'teacher' ? S.TEACHER : S.PROFILE;
        const expect = role === 'teacher' ? acc.staffId : acc.studentId;
        const err = form.querySelector('.login-err');
        if (id !== expect || password !== S.DEMO_PASSWORD) { err.hidden = false; return; }
        const profile = Object.assign({}, acc, { role: role });
        S.writeLogin(profile);
        S.DS.setProfile(profile);
        if (!location.hash || location.hash === '#/login') history.replaceState(null, '', location.pathname + location.search + '#/home');
        paintWho();
        S.render();
      });
    }
    const origRender = S.render;
    const NEED_LOGIN = { timetable: 1, course: 1, grades: 1 };
    S.render = function () {
      const route = S.parseHash().route || 'home';
      if (!S.readLogin() && route === 'login') { showLogin(); return; }
      document.body.classList.remove('login-mode');
      document.body.classList.toggle('public-mode', !S.readLogin());
      const brand = document.querySelector('.brand-name');
      if (brand) brand.textContent = S.readLogin() ? '東吳學生新入口' : '東吳大學';
      if (!S.readLogin() && NEED_LOGIN[route]) { location.hash = '#/login'; return; }
      paintWho();
      return origRender.apply(this, arguments);
    };
    S.$('#logout').addEventListener('click', () => {
      S.clearLogin();
      S.DS.setProfile(Object.assign({}, S.PROFILE, { role: null }));
      S.render();
    });

    S.render();
    const asks = q.getAll('asla');
    if (asks.length && S.openAsla) { S.openAsla(); asks.forEach(S.askAsla); }
  }).catch((err) => {
    S.$('#view').innerHTML = `<div class="empty">資料載入失敗：${S.esc(err && err.message)}</div>`;
  });
})();
