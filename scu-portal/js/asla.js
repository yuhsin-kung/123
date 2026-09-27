/* =========================================================================
 * asla.js — 阿斯拉：關鍵字先查出站內事實與要打開的頁面，再請語言模型改寫。
 * 關鍵字沒查到時，改問語言模型自己的知識。模型沒開就退回關鍵字原文。
 * -------------------------------------------------------------------------
 * 所有答案只帶你到「站內頁面」（hash 路由），不含任何外部網址。
 * 判斷順序：
 *   1. RULES 優先規則（正規表示式）：期中退選、我今天／明天的課、日期類問題、學分上下限
 *   2. parseTime 時段找課：「星期三下午有什麼課」→ 直接打開 #/course 並帶入條件
 *   3. INTENTS 意圖關鍵字計分（38 個意圖）
 *   4. 都沒命中 → 以字片段模糊比對「所有功能」清單，再不行就建議到「更多」搜尋
 * 每個答案：{ text, src, actions:[{label, hash}], autoHash? }
 * ========================================================================= */
(function () {
  'use strict';
  const S = window.SCU; const esc = S.esc; const DS = S.DS;
  const $ = (s) => document.querySelector(s);
  const SRC = '東吳學生新入口站內示範資料';

  /* ---- 共用答案產生器 ---- */
  function feat(id, lead) {
    const f = DS.getFeature(id);
    return { text: `${lead ? lead + '\n' : ''}可以到站內「${f.name}」頁：${f.desc}`, src: SRC, actions: [f.action ? { label: '打開' + f.name, act: f.action } : { label: `前往「${f.name}」`, hash: f.route }] };
  }
  function ev(id) { return DS.getEvents().find((e) => e.id === id); }
  function evLine(e) { return `${e.title}：${S.eventRange(e)}（${S.countdown(e).label}）`; }
  function nextOf(filter) { return DS.getEvents().filter((e) => S.eventEnd(e) >= S.today && filter(e)).sort((a, b) => a.start.localeCompare(b.start))[0]; }

  /* 我某一天的課 */
  function dayAnswer(offset) {
    const d = S.addDays(S.today, offset); const label = offset === 1 ? '明天' : offset === 2 ? '後天' : '今天';
    const hol = S.holidayOn(d); const wd = S.weekday(d);
    const list = (!hol && d >= S.SEMESTER.start && d <= S.SEMESTER.end) ? S.classesOn(d) : [];
    if (!list.length) return { text: `${label}（${S.fmtDate(d)}）${hol ? `是${hol.title}` : wd === 0 || wd === 6 ? '是週末' : ''}，沒有課。`, src: SRC + '（我的課表）', kind: 'today', actions: [{ label: '看我的課表', hash: '#/timetable' }] };
    let head = '';
    if (!offset) {
      const now = list.find((x) => x.startMin <= S.nowMin && x.endMin > S.nowMin);
      const next = list.find((x) => x.startMin > S.nowMin);
      head = now ? `現在正在上「${now.c.name}」（${now.c.room}）。` : next ? `下一堂是 ${next.startT}「${next.c.name}」（${next.c.room}）。` : '今天的課都上完了。';
      head += '\n';
    }
    return { text: `${head}${label}（${S.fmtDate(d)}）共 ${list.length} 堂：\n${list.map((x) => `・${x.startT}–${x.endT} ${x.c.name}｜${x.c.room}｜${x.c.teacher}`).join('\n')}`,
      src: SRC + '（我的課表）', kind: 'today', actions: [{ label: '回首頁看今天的課', hash: '#/home' }, { label: '完整課表', hash: '#/timetable' }] };
  }

  /* 日期類問題：從行事曆找 */
  const DATE_KEYS = [
    [/期中退/, (e) => e.id === 'middrop'], [/退修/, (e) => e.id === 'finaldrop'], [/初選/, (e) => e.id === 'prereg'],
    [/期中考/, (e) => e.id === 'midterm'], [/期末考/, (e) => e.id === 'final'], [/考試|考週/, (e) => e.type === 'exam'],
    [/加退選|加選|退選|選課/, (e) => e.type === 'course'], [/繳費|學費|學雜費/, (e) => e.id === 'fee' || e.id === 'fee2'],
    [/就貸|貸款|撥款/, (e) => e.id === 'loan'], [/獎學金/, (e) => e.id === 'scholarship'], [/寒假/, (e) => e.id === 'winter'],
    [/放假|連假|假日|休假|補假/, (e) => e.type === 'holiday'], [/開學/, (e) => e.id === 'start' || e.id === 'start2']
  ];
  function weekdayOffAnswer() {
    const start = S.SEMESTER.start, end = S.SEMESTER.end;
    const names = ['日', '一', '二', '三', '四', '五', '六'];
    const lines = [];
    const seen = new Set();
    DS.getEvents().forEach((e) => {
      if (e.type !== 'holiday') return;
      const from = e.start < start ? start : e.start;
      const to = S.eventEnd(e) > end ? end : S.eventEnd(e);
      if (to < start || e.start > end) return;
      const days = Math.round((new Date(to) - new Date(from)) / 86400000) + 1;
      if (days > 10) {
        lines.push(`・${e.title}：${S.fmtDate(from)}–${S.fmtDate(to)}（連續假期）`);
        return;
      }
      for (let d = from; d <= to; d = S.addDays(d, 1)) {
        const wd = S.weekday(d);
        if (wd < 1 || wd > 5 || seen.has(d)) continue;
        seen.add(d);
        lines.push(`・${S.fmtDate(d)}（星期${names[wd]}）${e.title}`);
      }
    });
    const src = SRC + '（行事曆，示範日期）';
    const actions = [{ label: '看行事曆', hash: '#/calendar' }];
    if (!lines.length) return { text: '這學期的行事曆裡，星期一到五沒有標成放假的日子。', src, actions };
    return { text: `這學期（${S.SEMESTER.label}）平日放假如下，週末本來就沒課，所以沒列：\n${lines.join('\n')}`, src, actions };
  }
  function dateAnswer(text) {
    for (const [re, f] of DATE_KEYS) {
      if (!re.test(text)) continue;
      const e = nextOf(f);
      if (!e) return { text: '這學期的行事曆裡沒有找到還沒結束的相關日期。', src: SRC + '（行事曆）', actions: [{ label: '看行事曆', hash: '#/calendar' }] };
      return { text: `${evLine(e)}。\n${e.desc || ''}`, src: SRC + '（行事曆，示範日期）', actions: (e.route && e.route !== '#/calendar' ? [{ label: '前往相關頁面', hash: e.route }] : []).concat([{ label: '看行事曆', hash: '#/calendar' }]) };
    }
    const up = S.upcomingEvents(3);
    return { text: `最近的全校事務：\n${up.map((e) => '・' + evLine(e)).join('\n')}`, src: SRC + '（行事曆，示範日期）', actions: [{ label: '看行事曆', hash: '#/calendar' }] };
  }

  const INTENTS = [
    { id: 'hello', kw: ['你好', '嗨', 'hi', 'hello', '你是誰', '能做什麼', '怎麼用', '幫助', 'help'],
      answer: () => ({ text: '嗨，我是阿斯拉！我可以告訴你今天有什麼課、學校事務的日期，也能帶你到站內各功能頁。\n試試：「今天有什麼課」「加退選什麼時候截止」「星期三下午有什麼課」。', src: SRC, actions: [{ label: '看所有功能', hash: '#/more' }] }) },
    { id: 'today', kw: ['今天有什麼課', '今天的課', '等一下', '下一堂', '下堂課', '幾點上課', '在哪上課', '教室在哪'], answer: () => dayAnswer(0) },
    { id: 'midterm-drop', kw: ['期中退選', '期中退', '期中停修', '期中棄選'],
      answer: () => { const e = ev('middrop'); return { text: `期中退選直接在本站「期中退選」頁辦理。\n${evLine(e)}。`, src: SRC, actions: [{ label: '前往「期中退選」', hash: '#/p/midterm-drop' }, { label: '看行事曆', hash: '#/calendar' }] }; } },
    { id: 'final-drop', kw: ['期末退修', '退修'], answer: () => feat('final-drop', evLine(ev('finaldrop')) + '。') },
    { id: 'add-drop', kw: ['加退選', '初選', '加選', '退選', '選課', '搶課'], not: ['期中', '期末', '輔導'],
      answer: () => { const e = nextOf((x) => x.type === 'course'); return { text: `選課在本站「選課」頁：先用「時段找課」加到選課車，送出前會自動檢查衝堂、學分（示範規則 16–25）與額滿。${e ? '\n' + evLine(e) + '。' : ''}`, src: SRC, actions: [{ label: '時段找課', hash: '#/course?tab=find' }, { label: '選課車＋送出前檢查', hash: '#/course?tab=cart' }] }; } },
    { id: 'conflict', kw: ['衝堂', '檢查', '擋修', '額滿', '名額'],
      answer: () => ({ text: '「選課車」會在送出前檢查衝堂、學分上下限（示範規則 16–25）和額滿；有問題會列出原因並推薦替代課程，全部通過才能送出。', src: SRC, actions: [{ label: '打開選課車', hash: '#/course?tab=cart' }] }) },
    { id: 'timetable', kw: ['我的課表', '課表', '功課表', '幾學分', '已選學分'], not: ['班級', '別班', '同學'],
      answer: () => { const my = S.myCourses(); return { text: `你這學期有 ${my.length} 門課、共 ${S.sumCredits(my)} 學分。「我的課表」會顯示每週課表和每門課的剩餘名額。`, src: SRC + '（我的課表）', actions: [{ label: '看我的課表', hash: '#/timetable' }] }; } },
    { id: 'class-tt', kw: ['班級課表', '別班', '同學的課表', '查班級', '班表'],
      answer: () => { const P = DS.getProfile(); return { text: `「我的課表」頁下方有「查班級課表」，已預設帶入你的班級（${P.program}・${P.dept} ${P.grade} 年級 ${P.cls} 班），可以改學制、系所、年級、班別查別班。`, src: SRC, actions: [{ label: '查班級課表', hash: '#/timetable?focus=class' }] }; } },
    { id: 'grades', kw: ['成績', '分數', '班排', '系排', '排名', '趴數', '操行', 'gpa', '平均'],
      answer: () => { const g = S.gradeSummary(); return { text: `本學期成績尚未公布。已公布的學期在「成績」頁：累計 GPA ${g.cum.gpa.toFixed(2)}（4.3 制示範換算），最近一學期（${g.latest.sem}）班排 ${g.latest.classRank[0]}/${g.latest.classRank[1]}、系排 ${g.latest.deptRank[0]}/${g.latest.deptRank[1]}。`, src: SRC + '（示範成績）', actions: [{ label: '看成績', hash: '#/grades' }] }; } },
    { id: 'graduate', kw: ['畢業', '學分進度', '還差', '畢業門檻', '畢業標準'],
      answer: () => { const g = S.gradeSummary(); const need = DS.getGradCredits(); return { text: `目前實得 ${g.cum.earned} 學分，畢業門檻 ${need} 學分（示範），還差 ${need - g.cum.earned} 學分（含本學期修課中的學分前）。`, src: SRC, actions: [{ label: '看畢業學分進度', hash: '#/grades?focus=grad' }] }; } },
    { id: 'calendar', kw: ['行事曆', '校曆', '重要日期'], answer: () => dateAnswer('') },
    { id: 'exam', kw: ['期中考', '期末考', '考試'], answer: (t) => dateAnswer(t) },
    { id: 'holiday', kw: ['放假', '連假', '寒假', '補假', '放掉', '停課'], answer: (t) => /放掉|停課|哪幾天|平日/.test(t) ? weekdayOffAnswer() : dateAnswer(t) },
    { id: 'loan', kw: ['就貸', '就學貸款', '助學貸款', '貸款', '撥款通知書', '對保'], answer: () => feat('loan', evLine(ev('loan')) + '。') },
    { id: 'fee', kw: ['學費', '繳費', '學雜費', '繳費單', '退費', '補費', '欠費'], answer: () => feat('fee', evLine(ev('fee')) + '。') },
    { id: 'scholar', kw: ['獎學金', '助學金', '獎助學金', '清寒', '補助'], answer: () => feat('scholarship') },
    { id: 'emergency', kw: ['急難', '救助', '經濟困難', '家裡出事'], answer: () => feat('emergency', '家裡遇到突發狀況，可以申請急難救助，也可以先找導師或系辦聊聊。') },
    { id: 'dorm', kw: ['宿舍', '住宿', '床位', '住校'], answer: () => feat('dorm') },
    { id: 'leave', kw: ['請假', '病假', '事假', '公假'], answer: () => feat('leave') },
    { id: 'reading', kw: ['閱覽室', '劃位', '自習座位'], answer: () => feat('reading-room') },
    { id: 'card', kw: ['悠遊卡', '學生證', '鎖卡', '掛失', '卡片不見', '卡不見'], answer: () => feat('card', '學生證（悠遊卡）遺失請先線上鎖卡。') },
    { id: 'double', kw: ['雙主修', '輔系', '跨領域', '學程', '雙輔跨'], answer: () => feat('double') },
    { id: 'second', kw: ['第二專長'], answer: () => feat('second') },
    { id: 'counsel', kw: ['諮商', '心理', '心情', '壓力', '焦慮', '難過', '憂鬱', '睡不著', '想找人聊'],
      answer: () => feat('counsel', '辛苦了，你不用一個人扛。可以預約心理諮商初談。若有立即危險，請先撥打 119 或 110。') },
    { id: 'insurance', kw: ['保險', '理賠', '學保', '受傷', '住院'], answer: () => feat('insurance') },
    { id: 'mail', kw: ['信箱', 'email', 'e-mail', 'mail', '郵件', 'webmail'], answer: () => feat('mail', '學校信箱帳號為學號（示範）。') },
    { id: 'news', kw: ['公告', '最新消息', '通知'], answer: () => feat('news') },
    { id: 'work', kw: ['工讀', '打工', '薪水', '時數', '出勤'], answer: () => feat('work') },
    { id: 'ta', kw: ['教學助理', '助教', 'ta'], answer: () => feat('ta') },
    { id: 'venue', kw: ['借教室', '場地', '租借', '空教室', '自習教室', '置物櫃', '器材'], answer: () => feat('venue') },
    { id: 'lost', kw: ['失物', '掉了', '遺失物', '海報', '反映'], not: ['學生證', '悠遊卡'], answer: () => feat('lost') },
    { id: 'club', kw: ['社團', '社長', '社團經費', '經歷認證'], answer: () => feat('club') },
    { id: 'event', kw: ['活動報名', '講座', '活動'], answer: () => feat('events') },
    { id: 'intern', kw: ['實習', '證照', '職涯'], answer: () => feat('intern') },
    { id: 'summer', kw: ['暑修', '暑期班'], answer: () => feat('summer') },
    { id: 'cards', kw: ['停車卡', '影印卡', '停車', '影印', '儲值'], answer: () => feat('cards') },
    { id: 'cert', kw: ['在學證明', '成績單'], answer: () => feat('cert') },
    { id: 'profile', kw: ['個人資料', '學號', '我是誰', '我的班級'], answer: () => feat('profile') }
  ];

  /* 優先規則 */
  const RULES = [
    { re: /放掉|停課|不用上課|哪幾天.*(放|假)|(平日|週間).*(放|假|停)/, answer: () => weekdayOffAnswer() },
    { re: /期中.*(退|停修|棄)/, answer: () => INTENTS.find((x) => x.id === 'midterm-drop').answer() },
    { re: /明天.*(課|上課)/, answer: () => dayAnswer(1) },
    { re: /後天.*(課|上課)/, answer: () => dayAnswer(2) },
    { re: /(今天|等一下|待會|下一堂|下堂|現在).*(課|上課|教室)/, answer: () => dayAnswer(0) },
    { re: /((最多|最少|上限|下限).*學分|學分.*(上限|下限)|修幾學分|超修)/, answer: () => ({
      text: `本站選課檢查用的是示範規則：每學期 ${DS.getCreditRule().min}–${DS.getCreditRule().max} 學分（正式規定以學校學則為準，尚待查證）。`, src: SRC + '（示範規則）', actions: [{ label: '檢查我的學分', hash: '#/course?tab=cart' }] }) },
    { re: /(截止|期限|什麼時候|何時|哪天|日期|幾號|時程|還有幾天|哪時候)/, answer: (t) => /成績|分數|gpa|排名|操行/.test(t) ? null : dateAnswer(t) }
  ];

  /* 時段找課：「星期三下午有什麼課」 */
  const DAYMAP = { '一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '日': 7, '天': 7, '1': 1, '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7 };
  const CN_NUM = { '一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10 };
  function num(s) { return /^\d+$/.test(s) ? +s : CN_NUM[s] || NaN; }
  function parseTime(text) {
    const dm = text.match(/(?:星期|週|周|禮拜|礼拜)\s*([一二三四五六日天1-7])/);
    const pm = text.match(/第?\s*([0-9一二三四五六七八九十]{1,2})\s*節?\s*(?:到|至|-|~|－|—)\s*第?\s*([0-9一二三四五六七八九十]{1,2})\s*節/);
    const single = text.match(/第\s*([0-9一二三四五六七八九十]{1,2})\s*節/);
    let from = null, to = null, label = '';
    if (pm) { from = num(pm[1]); to = num(pm[2]); label = `第 ${from}–${to} 節`; }
    else if (single) { from = to = num(single[1]); label = `第 ${from} 節`; }
    else if (/上午|早上|早八/.test(text)) { from = 1; to = 4; label = '上午（1–4 節）'; }
    else if (/中午/.test(text)) { from = 5; to = 5; label = '中午（第 5 節）'; }
    else if (/下午/.test(text)) { from = 6; to = 9; label = '下午（6–9 節）'; }
    else if (/晚上|傍晚/.test(text)) { from = 10; to = 10; label = '傍晚（第 10 節）'; }
    const courseWord = /課|空堂|有什麼|開什麼|找/.test(text);
    if (!dm && !(from && courseWord)) return null;
    if (dm && !courseWord && from == null) return null;
    const day = dm ? DAYMAP[dm[1]] : 3;
    if (!from || isNaN(from)) { from = 1; to = 10; label = label || '全天'; }
    if (isNaN(to)) to = from;
    from = Math.min(Math.max(from, 1), 10); to = Math.min(Math.max(to, 1), 10);
    if (from > to) { const t = from; from = to; to = t; }
    return { day, from, to, label, dayGiven: !!dm, type: /通識/.test(text) ? '通識' : /必修/.test(text) ? '必修' : /選修/.test(text) ? '選修' : '' };
  }
  /* 「星期三我有什麼課」是自己的課表。「星期三下午有什麼課」才是選課頁的全部開課。 */
  function asksOwnDay(text) {
    if (/找課|選課|加選|退選|可以選|哪些課|空堂|開什麼|通識/.test(text)) return false;
    if (/我/.test(text) && /課/.test(text)) return true;
    if (/有課嗎|有沒有課|有沒有上課|要上課|會上課|有上課|要不要上課|有我的課/.test(text)) {
      if (/第\s*[0-9一二三四五六七八九十]{1,2}\s*節|上午|下午|早上|晚上|中午|傍晚/.test(text)) return false;
      return true;
    }
    return false;
  }
  function myWeekdayAnswer(day) {
    const name = '星期' + S.WD[day];
    const actions = [{ label: '看我的課表', hash: '#/timetable' }];
    if (day < 1 || day > 5) return { text: `${name}沒有排課。`, src: SRC + '（我的課表）', kind: 'own', day: day, actions };
    const list = [];
    S.myCourses().forEach((c) => (c.slots || []).forEach((s) => {
      if (s.day === day) list.push({ c, s, startT: S.periodStart(s.start), endT: S.periodEnd(s.end) });
    }));
    list.sort((a, b) => a.s.start - b.s.start);
    if (!list.length) return { text: `${name}你沒有課。`, src: SRC + '（我的課表）', kind: 'own', day: day, actions };
    return { text: `${name}你有 ${list.length} 堂：\n${list.map((x) => `・${x.startT}–${x.endT} ${x.c.name}｜${x.c.room}｜${x.c.teacher}`).join('\n')}`,
      src: SRC + '（我的課表）', kind: 'own', day: day, actions };
  }
  function timeAnswer(t) {
    if (t.day > 5) return { text: `星期${t.day === 6 ? '六' : '日'}沒有開課（示範資料只有星期一到五）。`, src: SRC, actions: [{ label: '打開時段找課', hash: '#/course?tab=find' }] };
    const n = DS.getCourses().filter((c) => (!t.type || c.type === t.type) && c.slots.some((s) => s.day === t.day && s.start <= t.to && s.end >= t.from)).length;
    const hash = `#/course?tab=find&day=${t.day}&from=${t.from}&to=${t.to}${t.type ? '&type=' + encodeURIComponent(t.type) : ''}`;
    return { text: `星期${S.WD[t.day]}${t.label ? ' ' + t.label : ''}共有 ${n} 門${t.type || ''}課（示範資料）。我已經幫你打開「時段找課」並帶入條件，可以直接加選。${t.dayGiven ? '' : '\n（沒聽到星期幾，先用星期三示範）'}`,
      src: SRC + '（示範課程）', kind: 'find', actions: [{ label: '看結果', hash }], autoHash: hash };
  }

  function norm(s) { return String(s || '').toLowerCase().replace(/\s+/g, ''); }
  function answer(q) {
    const text = norm(q); if (!text) return null;
    for (const r of RULES) {
      if (!r.re.test(text)) continue;
      const a = r.answer(text);
      if (a) return a;
    }
    const ownDay = text.match(/(?:星期|週|周|禮拜|礼拜)\s*([一二三四五六日天1-7])/);
    if (ownDay && asksOwnDay(text)) return myWeekdayAnswer(DAYMAP[ownDay[1]]);
    const t = parseTime(q); if (t) return timeAnswer(t);
    let best = null, bestScore = 0;
    INTENTS.forEach((it) => {
      if (it.not && it.not.some((w) => text.indexOf(norm(w)) >= 0)) return;
      let score = 0;
      it.kw.forEach((k) => { const nk = norm(k); if (text.indexOf(nk) >= 0) score += nk.length >= 3 ? 2 : 1; });
      if (score > bestScore) { best = it; bestScore = score; }
    });
    if (best) return best.answer(text);
    const hits = fuzzy(text);
    if (hits.length) return { text: `我不太確定你的意思，這幾個功能可能相關：\n${hits.map((h) => '・' + h.name).join('\n')}`, src: SRC, actions: hits.map((h) => (h.action ? { label: h.name, act: h.action } : { label: h.name, hash: h.route })), miss: true };
    return { text: '站內功能對不到這句。', src: SRC, actions: [{ label: '在所有功能搜尋', hash: '#/more?q=' + encodeURIComponent(q) }], miss: true };
  }
  function fuzzy(text) {
    const out = [];
    DS.getFeatures().forEach((g) => g.items.forEach((it) => {
      let sc = 0;
      (it.kw || []).concat(it.subs || [], [it.name]).forEach((k) => { const nk = norm(k); for (let i = 0; i + 2 <= nk.length; i++) if (text.indexOf(nk.substr(i, 2)) >= 0) { sc++; break; } });
      if (sc) out.push(Object.assign({ sc }, it));
    }));
    return out.sort((a, b) => b.sc - a.sc).slice(0, 3);
  }
  S.aslaAnswer = answer; S.ASLA_INTENTS = INTENTS;

  /* ---------------- UI ---------------- */
  const panel = $('#asla-panel'), fab = $('#asla-fab'), log = $('#asla-log'), input = $('#asla-input');
  const CHIPS = ['今天有什麼課', '加退選什麼時候截止', '期中退選在哪', '星期三下午有什麼課', '我的 GPA', '學生證掉了', '我要辦就貸', '心情不好想找人聊'];
  $('#asla-chips').innerHTML = CHIPS.map((c) => `<button type="button" data-q="${esc(c)}">${esc(c)}</button>`).join('');

  const aslaHist = [];
  let lastCtx = null;

  function isFollowUp(text) {
    if (!text || text.length > 16) return false;
    return /^(那|那麼|所以|還有|然後|換|改)/.test(text) || /呢$/.test(text) || /^(星期|週|周|禮拜|礼拜)/.test(text);
  }
  /* 「那星期四呢」沿用上一題：有課嗎就還是查自己的課，不是重頭猜 */
  function expandFollow(q) {
    const text = norm(q);
    if (!lastCtx) return q;
    const dm = text.match(/(?:星期|週|周|禮拜|礼拜)\s*([一二三四五六日天1-7])/);
    const aboutMine = /有課|我有課|上課/.test(text) && !/找課|選課|可以選|哪些課|通識/.test(text);
    if ((lastCtx.kind === 'own' || lastCtx.kind === 'today') && aboutMine && !dm && text.length <= 12) {
      if (lastCtx.kind === 'own' && lastCtx.day) return '星期' + S.WD[lastCtx.day] + '有課嗎';
      return '今天有什麼課';
    }
    if (!isFollowUp(text)) return q;
    if ((lastCtx.kind === 'own' || lastCtx.kind === 'today') && dm) return '星期' + dm[1] + '有課嗎';
    if ((lastCtx.kind === 'own' || lastCtx.kind === 'today') && /後天/.test(text)) return '後天有課嗎';
    if ((lastCtx.kind === 'own' || lastCtx.kind === 'today') && /明天/.test(text)) return '明天有課嗎';
    if ((lastCtx.kind === 'own' || lastCtx.kind === 'today') && /今天/.test(text)) return '今天有什麼課';
    return q;
  }

  function addMsg(role, html) { const d = document.createElement('div'); d.className = 'msg ' + role; d.innerHTML = html; log.appendChild(d); log.scrollTop = log.scrollHeight; return d; }
  function botReply(a) {
    const acts = (a.actions || []).map((x, i) => `<button class="btn btn-sm ${i === 0 ? 'btn-primary' : ''}" type="button" ${x.act ? `data-aact="${esc(x.act)}"` : `data-hash="${esc(x.hash)}"`}>${esc(x.label)}</button>`).join('');
    const el = addMsg('bot', `<span class="asla-body">${esc(a.text)}</span><span class="src">來源：${esc(a.src)}</span>${acts ? `<span class="acts">${acts}</span>` : ''}`);
    if (a.autoHash) S.go(a.autoHash);
    return el;
  }
  function paint(el, text, src) {
    const body = el.querySelector('.asla-body');
    const from = el.querySelector('.src');
    if (body) body.textContent = text;
    if (from) from.textContent = '來源：' + src;
  }
  function askModel(q, local) {
    const now = (S.NOW && S.NOW.date) ? (S.NOW.date + 'T' + (S.NOW.time || '00:00')) : undefined;
    const payload = { message: q, history: aslaHist.slice(-8), now: now };
    if (local && !local.miss) { payload.mode = 'portal'; payload.facts = local.text; }
    else if (local && local.miss && lastCtx && isFollowUp(norm(q))) {
      payload.mode = 'portal';
      payload.facts = lastCtx.facts;
      payload.followup = true;
    }
    return fetch(S.ASLA_API, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }).then((r) => r.json());
  }
  const CAMPUS_RE = /東吳|學校|校園|學生|學號|科系|班級|課|選|成績|分數|學分|學年|學期|行事曆|校曆|放假|假期|連假|補假|國慶|中秋|春節|元旦|教師|宿舍|繳費|學費|學雜費|獎學金|公告|請假|圖書館|老師|教授|教室|節次|加退選|註冊|學生證|就貸|諮商|心情|社團|實習|畢業|操行|排名|名次|阿斯拉|入口/;
  const REFUSE = '這個問題和東吳或學生事務無關，我不回答。可以問我課表、選課、成績、行事曆或校園辦事。';
  function ask(q) {
    q = String(q || '').trim(); if (!q) return;
    addMsg('user', esc(q));
    const looked = expandFollow(q);
    const local = answer(looked);
    if (local && local.miss && !CAMPUS_RE.test(norm(q)) && !CAMPUS_RE.test(norm(looked))) {
      botReply({ text: REFUSE, src: '阿斯拉', actions: [] });
      return;
    }
    const el = botReply(local);
    if (local && !local.miss) lastCtx = { kind: local.kind || 'fact', facts: local.text, q: q, day: local.day };
    if (!S.ASLA_API) return;
    const src = el.querySelector('.src');
    if (src) src.textContent = '來源：阿斯拉改寫中…';
    askModel(q, local).then((data) => {
      const text = String((data && data.answer) || '').replace(/（這是上一題的事實[^）]*）/g, '').trim();
      if (!text) { paint(el, local.text, local.src); return; }
      const from = local.miss ? '阿斯拉語言模型' : local.src;
      paint(el, text, from);
      aslaHist.push({ role: 'user', content: q });
      aslaHist.push({ role: 'assistant', content: text.slice(0, 1500), route: data.route || (local.miss ? 'general' : 'portal') });
    }).catch(() => paint(el, local.text, local.src + '（語言模型未連線，改顯示站內原文）'));
  }
  function open(q) {
    placePanel();
    panel.hidden = false; fab.setAttribute('aria-expanded', 'true'); document.body.classList.add('asla-open');
    if (!log.childElementCount) botReply({ text: '嗨，我是阿斯拉。想知道什麼？直接用問的，我帶你到站內對應的頁面。', src: SRC });
    if (q) ask(q); else setTimeout(() => input.focus(), 30);
  }
  function close() { panel.hidden = true; fab.setAttribute('aria-expanded', 'false'); document.body.classList.remove('asla-open'); }
  S.openAsla = open; S.askAsla = ask;

  const FAB_KEY = 'asla-fab-pos';
  let fabAnchor = null;
  let fabFrac = null;
  function readFrac() {
    try { return JSON.parse(localStorage.getItem(FAB_KEY) || 'null'); } catch (e) { return null; }
  }
  function writeFrac(nx, ny) {
    fabFrac = { nx, ny };
    try { localStorage.setItem(FAB_KEY, JSON.stringify(fabFrac)); } catch (e) { /* 記不住就只留在這次畫面 */ }
  }
  function placePanel() {
    const r = fab.getBoundingClientRect();
    if (r.width) fabAnchor = { left: r.left, top: r.top, right: r.right, bottom: r.bottom, width: r.width, height: r.height };
    if (window.innerWidth < 900) {
      ['left', 'top', 'right', 'bottom', 'width', 'height'].forEach((k) => { panel.style[k] = ''; });
      return;
    }
    const a = fabAnchor || r;
    const margin = 12;
    const w = Math.min(390, window.innerWidth - margin * 2);
    const h = Math.min(620, window.innerHeight - margin * 2);
    let left = a.left + a.width / 2 > window.innerWidth / 2 ? a.left - w - margin : a.right + margin;
    if (left < margin) left = margin;
    if (left + w > window.innerWidth - margin) left = window.innerWidth - w - margin;
    let top = a.top + a.height / 2 > window.innerHeight / 2 ? a.bottom - h : a.top;
    if (top < margin) top = margin;
    if (top + h > window.innerHeight - margin) top = Math.max(margin, window.innerHeight - h - margin);
    panel.style.left = left + 'px';
    panel.style.top = top + 'px';
    panel.style.right = 'auto';
    panel.style.bottom = 'auto';
    panel.style.width = w + 'px';
    panel.style.height = h + 'px';
  }
  function placeFab(x, y) {
    if (getComputedStyle(fab).display === 'none') return { x, y };
    const size = fab.offsetWidth || 40;
    const maxX = Math.max(8, window.innerWidth - size - 8);
    const maxY = Math.max(8, window.innerHeight - size - 8);
    x = Math.min(Math.max(8, x), maxX);
    y = Math.min(Math.max(8, y), maxY);
    fab.style.left = x + 'px';
    fab.style.top = y + 'px';
    fab.style.right = 'auto';
    fab.style.bottom = 'auto';
    placePanel();
    return { x, y };
  }
  function applyFrac() {
    if (!fabFrac || !Number.isFinite(fabFrac.nx) || !Number.isFinite(fabFrac.ny)) return;
    const size = fab.offsetWidth || 40;
    placeFab(fabFrac.nx * Math.max(1, window.innerWidth - size), fabFrac.ny * Math.max(1, window.innerHeight - size));
  }
  fabFrac = readFrac();
  if (fabFrac && Number.isFinite(fabFrac.x) && !Number.isFinite(fabFrac.nx)) fabFrac = null;
  if (fabFrac) applyFrac();
  let lastW = window.innerWidth;
  window.addEventListener('resize', () => {
    const w = window.innerWidth;
    const widthChanged = Math.abs(w - lastW) > 48;
    lastW = w;
    if (!widthChanged) return;
    if (fabFrac) applyFrac();
    else if (!panel.hidden) placePanel();
  });
  let drag = null;
  fab.addEventListener('pointerdown', (e) => {
    if (e.button != null && e.button !== 0) return;
    const rect = fab.getBoundingClientRect();
    drag = { id: e.pointerId, dx: e.clientX - rect.left, dy: e.clientY - rect.top, sx: e.clientX, sy: e.clientY, moved: false };
    fab.setPointerCapture(e.pointerId);
  });
  fab.addEventListener('pointermove', (e) => {
    if (!drag || e.pointerId !== drag.id) return;
    if (Math.abs(e.clientX - drag.sx) + Math.abs(e.clientY - drag.sy) > 6) drag.moved = true;
    if (drag.moved) placeFab(e.clientX - drag.dx, e.clientY - drag.dy);
  });
  fab.addEventListener('pointerup', (e) => {
    if (!drag || e.pointerId !== drag.id) return;
    const moved = drag.moved;
    drag = null;
    if (!moved) return;
    fab.dataset.dragged = '1';
    const pos = placeFab(parseFloat(fab.style.left), parseFloat(fab.style.top));
    const size = fab.offsetWidth || 40;
    writeFrac(pos.x / Math.max(1, window.innerWidth - size), pos.y / Math.max(1, window.innerHeight - size));
  });
  fab.addEventListener('click', (e) => {
    if (fab.dataset.dragged === '1') { fab.dataset.dragged = ''; e.preventDefault(); e.stopPropagation(); return; }
    panel.hidden ? open() : close();
  });
  $('#asla-close').addEventListener('click', close);
  $('#asla-form').addEventListener('submit', (e) => { e.preventDefault(); const q = input.value; input.value = ''; ask(q); });
  $('#asla-chips').addEventListener('click', (e) => { const b = e.target.closest('button[data-q]'); if (b) ask(b.dataset.q); });
  log.addEventListener('click', (e) => {
    const b = e.target.closest('button[data-hash],button[data-aact]'); if (!b) return;
    if (b.dataset.hash) { S.go(b.dataset.hash); if (window.innerWidth < 720) close(); }
  });
})();
