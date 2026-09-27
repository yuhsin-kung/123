/* =========================================================================
 * data-features.js — 「更多／所有功能」清單（取代舊版 13 大類外部連結地圖）
 * -------------------------------------------------------------------------
 * 每個功能都是站內頁面，不連到任何外部網站：
 *   route 以 #/p/ 開頭 → 示範頁（js/pages/more.js 的 placeholder），顯示說明與示範資料
 *   其他 route          → 已完整建置的頁面（首頁、課表、選課、成績、行事曆）
 * 欄位：id, icon, name, desc, route, built(是否為完整頁面), subs(之後可辦理的項目), kw(搜尋與阿斯拉用關鍵字)
 * ========================================================================= */
var SCU = window.SCU = window.SCU || {};

SCU.FEATURES = [
  { cat: '課業與選課', items: [
    { id: 'course', icon: 'course', name: '選課', route: '#/course', built: true, desc: '時段找課、選課車、送出前檢查（衝堂／學分／額滿）。', kw: ['選課', '加選', '退選', '加退選', '初選', '找課', '搶課'] },
    { id: 'timetable', icon: 'table', name: '我的課表', route: '#/timetable', built: true, desc: '一週課表、剩餘名額與總學分。', kw: ['課表', '功課表', '上課時間', '教室'] },
    { id: 'midterm-drop', icon: 'undo', name: '期中退選', route: '#/p/midterm-drop', desc: '開放期間選擇要退選的課程（成績單註記 W，示範規則）。', subs: ['選擇退選課程', '退選紀錄查詢'], kw: ['期中退選', '期中退', '停修', '棄選'] },
    { id: 'final-drop', icon: 'out', name: '期末退修', route: '#/p/final-drop', desc: '學期末依授課教師規定申請退修。', subs: ['期末退修申請', '申請進度查詢'], kw: ['期末退修', '退修'] },
    { id: 'double', icon: 'target', name: '雙主修／輔系／學程', route: '#/p/double', desc: '申請、查詢條件與放棄。', subs: ['查詢申請條件', '線上申請', '歷年紀錄', '放棄申請'], kw: ['雙主修', '輔系', '跨領域', '學程', '雙輔跨'] },
    { id: 'second', icon: 'plus', name: '第二專長', route: '#/p/second', desc: '第二專長申請、選課、放棄與狀態查詢。', subs: ['第二專長申請', '第二專長選課', '放棄第二專長', '狀態查詢'], kw: ['第二專長', '專長'] },
    { id: 'summer', icon: 'sun', name: '暑修', route: '#/p/summer', desc: '暑期班報名與繳費。', subs: ['暑期班課程查詢', '報名', '繳費單'], kw: ['暑修', '暑期班'] },
    { id: 'feedback', icon: 'chat', name: '課程意見調查', route: '#/p/feedback', desc: '期中／期末課堂反應意見填寫。', subs: ['填寫課堂反應意見'], kw: ['課堂反應', '教學評量', '期末問卷', '意見調查'] }
  ]},
  { cat: '成績與畢業', items: [
    { id: 'grades', icon: 'chart', name: '成績', route: '#/grades', built: true, desc: '所有學期成績、GPA、班排系排一次看。', kw: ['成績', '分數', '班排', '系排', '排名', '趴數', '操行', 'gpa', '平均'] },
    { id: 'graduation', icon: 'cap', name: '畢業學分進度', route: '#/grades?focus=grad', built: true, desc: '已修學分與畢業門檻（在成績頁）。', kw: ['畢業', '學分進度', '還差', '畢業門檻', '畢業標準'] },
    { id: 'academic-care', icon: 'hands', name: '學業關懷', route: '#/p/academic-care', desc: '學業預警與關懷紀錄。', subs: ['預警科目查詢', '導師關懷紀錄'], kw: ['學業關懷', '預警', '二一', '被當'] },
    { id: 'cert', icon: 'file', name: '在學證明／成績單', route: '#/p/cert', desc: '申請在學證明、成績單。', subs: ['在學證明申請', '中英文成績單申請', '成績單郵寄登記'], kw: ['在學證明', '成績單', '證明'] }
  ]},
  { cat: '行事曆與通知', items: [
    { id: 'calendar', icon: 'calendar', name: '行事曆', route: '#/calendar', built: true, desc: '全校重要日期：選課、繳費、考試、放假。', kw: ['行事曆', '截止', '期限', '日期', '放假', '考試週', '期中考', '期末考'] },
    { id: 'news', icon: 'horn', name: '公告', route: '#/p/news', desc: '學校與系所公告（示範內容）。', kw: ['公告', '消息', '最新消息', '通知'] },
    { id: 'mail', icon: 'mail', name: '校園信箱', route: '#/p/mail', desc: '學校信箱收件匣（示範內容）。', kw: ['信箱', 'email', 'e-mail', 'mail', '郵件', 'webmail'] }
  ]},
  { cat: '繳費與財務', items: [
    { id: 'fee', icon: 'pay', name: '學雜費繳費', route: '#/p/fee', desc: '本學期繳費單、繳費狀態與截止日。', subs: ['繳費單', '繳費狀態', '退補費查詢'], kw: ['學費', '繳費', '學雜費', '繳費單', '退費', '補費', '欠費'] },
    { id: 'loan', icon: 'bank', name: '就學貸款', route: '#/p/loan', desc: '線上申請、上傳撥款通知書、差額繳費單。', subs: ['線上就貸申請', '上傳撥款通知書', '差額繳費單', '貸款進度'], kw: ['就貸', '就學貸款', '助學貸款', '貸款', '撥款通知書', '對保'] },
    { id: 'cards', icon: 'park', name: '停車卡／影印卡', route: '#/p/cards', desc: '儲值紀錄與餘額。', subs: ['停車卡儲值紀錄', '影印卡餘額'], kw: ['停車卡', '影印卡', '停車', '影印', '儲值'] }
  ]},
  { cat: '獎助學金', items: [
    { id: 'scholarship', icon: 'medal', name: '獎助學金', route: '#/p/scholarship', desc: '可申請項目、申請與得獎紀錄。', subs: ['可申請獎學金', '申請紀錄', '得獎紀錄'], kw: ['獎學金', '助學金', '獎助學金', '清寒', '補助'] },
    { id: 'emergency', icon: 'life', name: '急難救助', route: '#/p/emergency', desc: '家庭突發變故時的急難救助申請。', subs: ['急難救助申請'], kw: ['急難', '救助', '經濟困難', '家裡出事'] }
  ]},
  { cat: '住宿與生活', items: [
    { id: 'dorm', icon: 'home', name: '宿舍', route: '#/p/dorm', desc: '宿舍申請、床位選填與申請狀態。', subs: ['宿舍申請', '床位選填', '申請狀態'], kw: ['宿舍', '住宿', '床位', '住校'] },
    { id: 'leave', icon: 'thermo', name: '請假', route: '#/p/leave', desc: '線上請假與請假紀錄。', subs: ['線上請假', '請假紀錄'], kw: ['請假', '病假', '事假', '公假'] },
    { id: 'reading-room', icon: 'book', name: '閱覽室劃位', route: '#/p/reading-room', desc: '閱覽室座位預約。', subs: ['座位預約', '我的預約'], kw: ['閱覽室', '劃位', '座位', '自習'] },
    { id: 'card', icon: 'id', name: '學生證／悠遊卡', route: '#/p/card', desc: '遺失時線上鎖卡、補辦說明。', subs: ['線上鎖卡', '補辦申請'], kw: ['悠遊卡', '學生證', '鎖卡', '掛失', '卡片不見', '卡不見'] }
  ]},
  { cat: '校園服務與活動', items: [
    { id: 'venue', icon: 'building', name: '場地借用', route: '#/p/venue', desc: '自習教室、空教室、置物櫃、社團器材。', subs: ['空教室查詢', '場地租借', '置物櫃'], kw: ['借教室', '場地', '租借', '空教室', '自習教室', '置物櫃', '器材'] },
    { id: 'lost', icon: 'search', name: '失物招領與反映', route: '#/p/lost', desc: '失物招領、校園問題反映、海報欄申請。', subs: ['失物招領', '問題反映', '海報欄申請'], kw: ['失物', '掉了', '遺失物', '海報', '反映'] },
    { id: 'events', icon: 'mic', name: '活動報名', route: '#/p/events', desc: '講座與校園活動報名。', subs: ['活動列表', '我的報名'], kw: ['活動報名', '講座', '活動'] },
    { id: 'club', icon: 'masks', name: '社團', route: '#/p/club', desc: '社團登錄、改選、經費申請、經歷認證。', subs: ['期初登錄', '期末改選', '經費申請', '經歷認證'], kw: ['社團', '社長', '社團經費', '經歷認證'] }
  ]},
  { cat: '工讀與職涯', items: [
    { id: 'work', icon: 'bag', name: '工讀時數／薪資', route: '#/p/work', desc: '工讀出勤時數登錄與薪資查詢。', subs: ['出勤時數登錄', '薪資查詢'], kw: ['工讀', '打工', '薪水', '時數', '出勤'] },
    { id: 'ta', icon: 'board', name: '教學助理', route: '#/p/ta', desc: 'TA 申請與線上確認。', subs: ['TA 申請', '線上確認'], kw: ['教學助理', '助教', 'ta'] },
    { id: 'intern', icon: 'compass', name: '實習與證照', route: '#/p/intern', desc: '實習作業與證照獎勵申請。', subs: ['實習登錄', '證照獎勵申請'], kw: ['實習', '證照', '職涯', '求職'] }
  ]},
  { cat: '健康與保險', items: [
    { id: 'counsel', icon: 'heart', name: '諮商預約', route: '#/p/counsel', desc: '心理諮商初談預約與身心健康資源。', subs: ['初談預約', '我的預約'], kw: ['諮商', '心理', '心情', '壓力', '焦慮', '難過', '憂鬱', '睡不著'] },
    { id: 'insurance', icon: 'shield', name: '學生保險', route: '#/p/insurance', desc: '學生團體保險理賠申請。', subs: ['理賠申請', '理賠進度'], kw: ['保險', '理賠', '學保', '受傷', '住院'] }
  ]},
  { cat: '個人與設定', items: [
    { id: 'profile', icon: 'user', name: '個人資料', route: '#/p/profile', desc: '基本資料與照片顯示設定（示範）。', subs: ['基本資料', '照片顯示設定'], kw: ['個人資料', '照片', '聯絡資料'] },
    { id: 'asla', icon: 'chat', name: '阿斯拉助手', action: 'open-asla', built: true, desc: '用問的找功能：「期中退選在哪」「今天有什麼課」。', kw: ['阿斯拉', '助手', '聊天'] },
    { id: 'settings', icon: 'gear', name: '示範設定', route: '#/settings', built: true, desc: '切換示範日期時間、重設示範資料。', kw: ['設定', '示範', '重設', '日期'] }
  ]}
];

SCU.featureById = function (id) {
  for (const g of SCU.FEATURES) for (const it of g.items) if (it.id === id) return Object.assign({ catName: g.cat }, it);
  return null;
};

/* 示範頁用的假資料（公告、信箱） */
SCU.NEWS = [
  { date: '2026-09-29', unit: '註冊課務組', title: '加退選將於 10/2（五）截止，請於期限內確認課表', tag: '選課' },
  { date: '2026-09-28', unit: '資料科學系', title: '115-1 系週會時間調整為 10/7（三）第 5 節', tag: '系所' },
  { date: '2026-09-26', unit: '出納組', title: '學雜費繳費截止日為 10/8（四），逾期將影響註冊', tag: '繳費' },
  { date: '2026-09-23', unit: '圖書館', title: '閱覽室期中考週延長開放時間公告', tag: '生活' },
  { date: '2026-09-18', unit: '生涯發展中心', title: '10 月企業參訪與實習說明會開放報名', tag: '活動' },
  { date: '2026-09-15', unit: '德育中心', title: '就學貸款撥款通知書請於 10/16 前上傳', tag: '繳費' }
];
SCU.MAILS = [
  { date: '2026-09-30', from: '資料視覺化 助教', title: '第 3 週作業繳交提醒（週五 23:59 截止）', unread: true },
  { date: '2026-09-29', from: '註冊課務組', title: '【提醒】加退選即將截止', unread: true },
  { date: '2026-09-27', from: '學生會', title: '迎新週活動照片已上傳', unread: false },
  { date: '2026-09-25', from: '圖書館', title: '您借閱的書籍將於 10/3 到期', unread: false },
  { date: '2026-09-22', from: '導師 陳老師', title: '本學期導生聚時間調查', unread: false }
];
