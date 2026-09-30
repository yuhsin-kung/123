/* =========================================================================
 * data-source.js — 資料存取層（頁面程式「只」透過這裡拿資料）
 * -------------------------------------------------------------------------
 * 目前：全部讀取本機示範 JS 資料（data-*.js、profile.js）＋ localStorage，完全離線。
 * 之後：改成 Python 後端（爬蟲 → SQLite → API）時，只要改這個檔案，
 *       頁面程式（core.js、pages/*.js、asla.js）都不用動。
 *
 * 使用方式：
 *   1. main.js 先呼叫 await SCU.DS.init()  → 把資料載入快取
 *      （之後可改成 fetch('/api/courses')、fetch('/api/events')…）
 *   2. 之後頁面用同步 getter 讀快取：getCourses()、getMyTimetable()、getEvents()…
 *   3. 需要即時查詢的（班級課表）回傳 Promise：await getClassTimetable(...)
 *
 * 對照未來 API（建議）：
 *   getProfile()                          ← GET  /api/profile
 *   getCourses() / getPeriods()           ← GET  /api/courses、/api/periods
 *   getMyTimetable() / saveMyTimetable()  ← GET/PUT /api/me/timetable
 *   getClassTimetable(學制,系所,年級,班別) ← GET  /api/class-timetable?program=&dept=&grade=&cls=
 *   getEvents()                           ← GET  /api/events
 *   getGrades()                           ← GET  /api/me/grades
 * ========================================================================= */
(function () {
  'use strict';
  const S = window.SCU;

  /* ---- localStorage（示範用的「後端儲存」）---- */
  const PREFIX = 'scu4.'; /* 課表改過一門課，不要沿用瀏覽器裡舊的選課 */
  const store = {
    get(k, d) { try { const v = localStorage.getItem(PREFIX + k); return v ? JSON.parse(v) : d; } catch (e) { return d; } },
    set(k, v) { try { localStorage.setItem(PREFIX + k, JSON.stringify(v)); } catch (e) { /* file:// 某些瀏覽器禁用，仍可在記憶體中運作 */ } },
    del(k) { try { localStorage.removeItem(PREFIX + k); } catch (e) { /* ignore */ } }
  };

  const cache = {};
  const byCode = {};

  const DS = {
    source: 'local-demo', /* 之後改 'api' */

    /* 載入資料到快取。現在是同步讀本機資料，包成 Promise 以便之後換成 fetch。 */
    init() {
      cache.profile = Object.assign({}, S.readLogin() || S.PROFILE);
      cache.periods = S.PERIODS.slice();
      cache.courses = S.COURSES.slice();
      cache.courses.forEach((c) => { byCode[c.code] = c; });
      cache.events = S.EVENTS.slice().sort((a, b) => a.start.localeCompare(b.start));
      cache.eventTypes = S.EVENT_TYPES;
      cache.grades = S.GRADES.slice();
      cache.creditRule = Object.assign({}, S.CREDIT_RULE);
      cache.classOptions = S.CLASS_OPTIONS;
      cache.features = S.FEATURES;
      cache.news = S.NEWS.slice();
      cache.mails = S.MAILS.slice();
      return Promise.resolve();
      /* 之後範例：
       * return Promise.all([fetch('/api/profile'), fetch('/api/courses'), fetch('/api/events')])
       *   .then((rs) => Promise.all(rs.map((r) => r.json())))
       *   .then(([p, c, e]) => { cache.profile = p; cache.courses = c; cache.events = e; ... });
       */
    },

    getProfile: () => cache.profile,
    setProfile(p) { cache.profile = Object.assign({}, p); },
    getPeriods: () => cache.periods,
    getCourses: () => cache.courses,
    getCourse: (code) => byCode[String(code || '').trim().toUpperCase()] || null,
    getCreditRule: () => cache.creditRule,
    getEvents: () => cache.events,
    getEventTypes: () => cache.eventTypes,
    getGrades: () => cache.grades,
    getGpaScale: () => S.GPA_SCALE,
    getGradCredits: () => S.GRAD_CREDITS,
    getClassOptions: () => cache.classOptions,
    getFeatures: () => cache.features,
    getFeature: (id) => S.featureById(id),
    /* 這台電腦上各功能被打開的次數。常用功能依這個排序，不上傳。 */
    useCounts: () => store.get('use', {}),
    bumpUse(id) {
      if (!id) return;
      const u = store.get('use', {});
      u[id] = (u[id] || 0) + 1;
      store.set('use', u);
    },
    /* 這台電腦上「全部功能」細項（SCU.MENU 的細項名稱）被點的次數。首頁「最近常用」依這個排序，不上傳。 */
    leafUse: () => store.get('leafUse', {}),
    bumpLeaf(label) {
      if (!label) return;
      const u = store.get('leafUse', {});
      u[label] = (u[label] || 0) + 1;
      store.set('leafUse', u);
    },
    featureForHash(hash) {
      const path = String(hash || '').replace(/^#/, '');
      if (!path || path === '/home' || path.startsWith('/home?')) return null;
      let best = null;
      (S.FEATURES || []).forEach((g) => g.items.forEach((it) => {
        if (!it.route) return;
        const r = it.route.replace(/^#/, '');
        if (path === r || path.startsWith(r + '/') || path.startsWith(r + '?')) {
          if (!best || r.length > best.route.replace(/^#/, '').length) best = it;
        }
      }));
      return best;
    },
    getNews: () => cache.news,     /* 之後 ← GET /api/news */
    getMails: () => cache.mails,   /* 之後 ← GET /api/me/mails */
    getDepts: () => S.DEPTS.concat(['通識教育中心', '體育室']),

    /* 班級課表：回傳 Promise<{ codes:[], note }>，之後改 fetch('/api/class-timetable?...') */
    getClassTimetable(program, dept, grade, cls) {
      const key = [program, dept, grade, cls].join('|');
      const codes = S.CLASS_TIMETABLES[key];
      return Promise.resolve(codes
        ? { codes: codes.slice(), note: '' }
        : { codes: [], note: program === '學士班' ? '查無此班級的示範資料。' : `目前示範資料只有「學士班」，${program}待接上資料庫後提供。` });
    },

    /* 我的課表與選課相關（目前存 localStorage；之後改 /api/me/...） */
    getMyTimetable: () => store.get('timetable', S.DEFAULT_TIMETABLE.slice()),
    saveMyTimetable: (codes) => store.set('timetable', codes),
    getCart: () => store.get('cart', { add: [], drop: [] }),
    saveCart: (cart) => store.set('cart', cart),
    getSeatDelta: () => store.get('seatDelta', {}),
    saveSeatDelta: (d) => store.set('seatDelta', d),
    getWithdrawn: () => store.get('withdrawn', []),
    saveWithdrawn: (w) => store.set('withdrawn', w),
    resetMyData() { ['timetable', 'cart', 'seatDelta', 'withdrawn'].forEach(store.del); },
    defaultTimetable: () => S.DEFAULT_TIMETABLE.slice()
  };
  S.DS = DS;
})();
