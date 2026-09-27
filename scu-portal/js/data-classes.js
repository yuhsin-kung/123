/* =========================================================================
 * data-classes.js — 示範「班級課表」資料（模擬之後爬蟲 + SQLite 的內容）
 * -------------------------------------------------------------------------
 * CLASS_OPTIONS     查班級課表的下拉選單選項：學制／系所／年級／班別
 * CLASS_TIMETABLES  鍵為 "學制|系所|年級|班別"，值為課程代碼陣列
 *                   目前只有「學士班」有示範資料：少數班級手動指定，其餘由下方
 *                   小程式依 data-courses.js 自動排出（同系同年級課程＋通識／體育，不衝堂）。
 * 之後改接後端時，這個檔案可以整個移除，由 data-source.js 的
 * getClassTimetable() 改呼叫 /api/class-timetable 取得。
 * ========================================================================= */
var SCU = window.SCU = window.SCU || {};

if (!SCU.CLASS_OPTIONS || !SCU.CLASS_OPTIONS.depts || !SCU.CLASS_OPTIONS.depts.length) SCU.CLASS_OPTIONS = {
  programs: ['學士班', '進修學士班', '碩士班'],
  depts: SCU.DEPTS.slice(),
  grades: [1, 2, 3, 4],
  classes: ['A', 'B']
};

(function () {
  if (SCU.CLASS_TIMETABLES) return;
  /* 手動指定（示範學生所在的班級） */
  const manual = {
    '學士班|資料科學系|3|B': ['DS301', 'DS302', 'DS304', 'DS203', 'GE102', 'PE102', 'GE106', 'CL101'],
    '學士班|資料科學系|3|A': ['DS303', 'DS302', 'DS304', 'DS305', 'GE106', 'PE101', 'EN102'],
    '學士班|資料科學系|2|B': ['DS201', 'DS202', 'DS203', 'GE104', 'PE102', 'EN102']
  };
  function overlaps(a, b) {
    return a.slots.some((x) => b.slots.some((y) => x.day === y.day && x.start <= y.end && y.start <= x.end));
  }
  function build(dept, grade, cls) {
    const pool = SCU.COURSES.filter((c) => c.dept === dept && (c.grade === grade || (grade === 4 && c.grade === 3)))
      .concat(SCU.COURSES.filter((c) => c.grade === 0));
    if (cls === 'B') pool.reverse(); /* A、B 班排課順序不同，模擬不同班級課表 */
    const picked = [];
    pool.forEach((c) => { if (picked.length < 8 && !picked.some((p) => overlaps(p, c))) picked.push(c); });
    return picked.map((c) => c.code);
  }
  const table = {};
  SCU.CLASS_OPTIONS.depts.forEach((d) => SCU.CLASS_OPTIONS.grades.forEach((g) => SCU.CLASS_OPTIONS.classes.forEach((k) => {
    const key = ['學士班', d, g, k].join('|');
    table[key] = manual[key] || build(d, g, k);
  })));
  SCU.CLASS_TIMETABLES = table;
})();
