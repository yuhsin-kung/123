/* =========================================================================
 * data-calendar.js — 115 學年度第 1 學期 示範行事曆（日期為示範，非學校公告）
 * -------------------------------------------------------------------------
 * 首頁「全校事務快到了」與「行事曆」頁共用這份資料；
 * type 為 holiday 的日子，首頁「今天的課」會顯示「放假，沒有課」。
 * 欄位：start/end（YYYY-MM-DD，單日活動 end 可省略）、type、title、desc、route（站內相關頁面）
 * type：course 選課／fee 繳費／exam 考試／holiday 放假／school 學校活動
 * ========================================================================= */
var SCU = window.SCU = window.SCU || {};

SCU.EVENT_TYPES = {
  course:  { name: '選課', cls: 'ev-course' },
  fee:     { name: '繳費', cls: 'ev-fee' },
  exam:    { name: '考試', cls: 'ev-exam' },
  holiday: { name: '放假', cls: 'ev-holiday' },
  school:  { name: '學校', cls: 'ev-school' }
};

SCU.EVENTS = [
  { id: 'start',        start: '2026-09-14', type: 'school',  title: '開學・第一週上課', desc: '115 學年度第 1 學期開始上課。', route: '#/timetable' },
  { id: 'adddrop',      start: '2026-09-21', end: '2026-10-02', type: 'course', title: '加退選', desc: '可在「選課」頁加選、退選，送出前會先檢查衝堂、學分與名額。', route: '#/course' },
  { id: 'midautumn',    start: '2026-09-25', type: 'holiday', title: '中秋節放假', desc: '全校停課一天。', route: '#/calendar' },
  { id: 'teacher',      start: '2026-09-28', type: 'holiday', title: '教師節放假', desc: '全校停課一天。', route: '#/calendar' },
  { id: 'fee',          start: '2026-10-08', type: 'fee',     title: '學雜費繳費截止', desc: '逾期未繳可能影響選課與註冊。可在「學雜費繳費」頁看繳費單。', route: '#/p/fee' },
  { id: 'national',     start: '2026-10-09', type: 'holiday', title: '國慶日補假', desc: '10/10 國慶日逢週六，於 10/9（五）補假。', route: '#/calendar' },
  { id: 'loan',         start: '2026-10-16', type: 'fee',     title: '就學貸款撥款通知書上傳截止', desc: '完成對保後，把撥款通知書上傳到「就學貸款」頁。', route: '#/p/loan' },
  { id: 'scholarship',  start: '2026-10-19', end: '2026-10-30', type: 'school', title: '校內獎學金申請', desc: '在「獎助學金」頁查看可申請項目。', route: '#/p/scholarship' },
  { id: 'midterm',      start: '2026-11-09', end: '2026-11-13', type: 'exam',   title: '期中考週', desc: '請留意各科考試時間與教室。', route: '#/timetable' },
  { id: 'middrop',      start: '2026-11-16', end: '2026-11-27', type: 'course', title: '期中退選', desc: '開放期間可在「期中退選」頁申請退選，成績單將註記 W（示範規則）。', route: '#/p/midterm-drop' },
  { id: 'finaldrop',    start: '2026-12-14', end: '2026-12-18', type: 'course', title: '期末退修申請', desc: '依授課教師規定辦理（示範）。', route: '#/p/final-drop' },
  { id: 'constitution', start: '2026-12-25', type: 'holiday', title: '行憲紀念日放假', desc: '全校停課一天。', route: '#/calendar' },
  { id: 'prereg',       start: '2026-12-28', end: '2027-01-06', type: 'course', title: '115-2 選課初選', desc: '下學期課程初選，可先用「時段找課」排好。', route: '#/course' },
  { id: 'newyear',      start: '2027-01-01', type: 'holiday', title: '元旦放假', desc: '開國紀念日。', route: '#/calendar' },
  { id: 'final',        start: '2027-01-04', end: '2027-01-08', type: 'exam',   title: '期末考週', desc: '期末考試，成績約於考後兩週公布（示範）。', route: '#/grades' },
  { id: 'winter',       start: '2027-01-18', end: '2027-02-21', type: 'holiday', title: '寒假', desc: '寒假期間不上課。', route: '#/calendar' },
  { id: 'fee2',         start: '2027-02-12', type: 'fee',     title: '115-2 學雜費繳費截止', desc: '下學期學雜費。', route: '#/p/fee' },
  { id: 'adddrop2',     start: '2027-02-22', end: '2027-03-05', type: 'course', title: '115-2 加退選', desc: '下學期加退選。', route: '#/course' },
  { id: 'start2',       start: '2027-02-22', type: 'school',  title: '115-2 開學', desc: '下學期開始上課。', route: '#/timetable' }
];
