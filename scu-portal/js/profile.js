/* =========================================================================
 * profile.js — 示範「已登入學生」資料（全站唯一的學生身分來源）
 * -------------------------------------------------------------------------
 * 之後接上登入與 Python 後端時，改由 js/data-source.js 的 getProfile()
 * 向 /api/profile 取得；這裡的值只是離線示範用的預設值。
 * 用途：頁首右上角小字顯示、課表頁「查班級課表」下拉選單自動帶入、
 *       時段找課標記本系課程、首頁問候。
 * ========================================================================= */
var SCU = window.SCU = window.SCU || {};

SCU.PROFILE = {
  role: 'student',
  name: '王小明',
  studentId: '11316025',
  program: '學士班',
  dept: '資料科學系',
  grade: 3,
  cls: 'B',
  campus: '城中校區'
};

/* 教師登入。課表改成「老師姓名出現在授課教師欄」的課，不是學生選課。 */
SCU.TEACHER = {
  role: 'teacher',
  name: '李家萱',
  staffId: 'T2019001',
  title: '助理教授',
  dept: '資料科學系',
  campus: '城中校區'
};

SCU.DEMO_PASSWORD = 'demo1234';
SCU.LOGIN_KEY = 'scu-login';

SCU.readLogin = function () {
  try { return JSON.parse(localStorage.getItem(SCU.LOGIN_KEY) || 'null'); } catch (e) { return null; }
};
SCU.writeLogin = function (profile) {
  const copy = Object.assign({}, profile);
  delete copy.password;
  localStorage.setItem(SCU.LOGIN_KEY, JSON.stringify(copy));
};
SCU.clearLogin = function () { localStorage.removeItem(SCU.LOGIN_KEY); };
