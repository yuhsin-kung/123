"""全功能助理 UI＋HTTP API（v2；標準庫 HTTP，不依賴 Gradio）。

原本的 chat_ui.py（7860）保持不動；這支是新版本，預設跑在 7861：
    start_chat_v2.bat   →   http://127.0.0.1:7861
（切換到 7860 的步驟見 README「切換到 v2」）
  GET  /              聊天頁面（交易 chips 照舊，另加學校／一般 chips，顯示路由與出處）
  POST /ask           舊介面 {q} → {answer}（相容保留，現在也會經過路由器）
  POST /api/chat      新 API {message, history?, profile?, mode?} → {answer, route, sources[], ...}
  GET  /api/health    健康檢查（stores、模型、門檻）
只綁 127.0.0.1（本機）；之後網站由 Django 後端代理呼叫 /api/chat。
"""
from __future__ import annotations

import json
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from pathlib import Path

from chatbot import chat

ROOT = Path(__file__).resolve().parents[1]
STATIC_CHARTS = ROOT / "static" / "charts"

import os

HOST = "127.0.0.1"  # 只綁本機
PORT = int(os.environ.get("TRADE_RAG_PORT", "7861"))

PAGE = """<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>trade-rag · 全功能助理</title>
  <style>
    :root {
      --bg: #0e1117;
      --card: #161b22;
      --line: #30363d;
      --txt: #e6edf3;
      --dim: #8b949e;
      --red: #e53935;
      --green: #3fb950;
      --acc: #58a6ff;
      --acc-bg: #1f6feb;
      --user: #1a2332;
      --bot: #161b22;
    }
    * { box-sizing: border-box; }
    html, body {
      margin: 0; height: 100%;
      background: var(--bg); color: var(--txt);
      font: 15px/1.5 "Segoe UI", "Microsoft JhengHei", "Noto Sans TC", sans-serif;
    }
    .app {
      max-width: 860px; margin: 0 auto; height: 100%;
      display: flex; flex-direction: column; padding: 0 1rem;
    }
    header {
      display: flex; justify-content: space-between; align-items: flex-start;
      padding: 1.1rem 0 0.75rem; border-bottom: 1px solid var(--line);
      flex-shrink: 0;
    }
    header h1 { margin: 0; font-size: 1.25rem; font-weight: 700; letter-spacing: 0.01em; }
    header .sub { margin: 0.25rem 0 0; color: var(--dim); font-size: 0.85rem; }
    .status { display: flex; gap: 0.45rem; align-items: center; color: var(--dim); font-size: 0.82rem; }
    .dot {
      width: 9px; height: 9px; border-radius: 50%; background: var(--green);
      box-shadow: 0 0 0 3px rgba(63,185,80,0.18);
    }
    .chips { display: flex; flex-wrap: wrap; gap: 0.4rem; padding: 0.75rem 0 0.4rem; flex-shrink: 0; }
    .chip {
      background: var(--card); color: var(--dim); border: 1px solid var(--line);
      border-radius: 999px; padding: 0.32rem 0.75rem; font-size: 0.78rem; cursor: pointer;
      transition: border-color .15s, color .15s, background .15s;
    }
    .chip:hover { border-color: var(--acc); color: var(--acc); background: rgba(88,166,255,0.08); }
    #log {
      flex: 1; overflow-y: auto; padding: 0.6rem 0 1rem;
      display: flex; flex-direction: column; gap: 0.65rem;
    }
    .bubble {
      border: 1px solid var(--line); border-radius: 12px;
      padding: 0.85rem 1rem; white-space: pre-wrap; word-break: break-word;
      max-width: 92%; animation: fadeIn .18s ease;
    }
    @keyframes fadeIn {
      from { opacity: 0; transform: translateY(4px); }
      to { opacity: 1; transform: none; }
    }
    .bubble .who {
      display: block; font-size: 0.72rem; font-weight: 600; letter-spacing: 0.04em;
      text-transform: uppercase; color: var(--dim); margin-bottom: 0.35rem;
    }
    .q { align-self: flex-end; background: var(--user); border-color: #2a3a4f; }
    .q .who { color: var(--acc); }
    .a { align-self: flex-start; background: var(--bot); }
    .a .who { color: var(--green); }
    .a.pending { color: var(--dim); font-style: italic; }
    .a.err { border-color: rgba(229,57,53,0.45); color: #ffb4b0; }
    .bubble img.chart {
      display: block; max-width: 100%; border-radius: 10px;
      border: 1px solid var(--line); margin-top: 0.6rem;
    }
    .composer {
      flex-shrink: 0; border-top: 1px solid var(--line);
      padding: 0.85rem 0 1.1rem; display: flex; gap: 0.55rem; align-items: flex-end;
    }
    textarea {
      flex: 1; min-height: 52px; max-height: 140px; resize: vertical;
      background: #0d1117; color: var(--txt); border: 1px solid var(--line);
      border-radius: 10px; padding: 0.65rem 0.8rem; font: inherit; line-height: 1.45;
      outline: none; transition: border-color .15s;
    }
    textarea:focus { border-color: var(--acc); box-shadow: 0 0 0 3px rgba(88,166,255,0.15); }
    textarea::placeholder { color: #6e7681; }
    button.send {
      background: var(--acc-bg); color: #fff; border: 1px solid var(--acc-bg);
      border-radius: 10px; padding: 0.65rem 1.15rem; font: inherit; font-weight: 600;
      cursor: pointer; white-space: nowrap; transition: filter .15s, opacity .15s;
    }
    button.send:hover { filter: brightness(1.08); }
    button.send:disabled { opacity: 0.55; cursor: wait; }
    .foot {
      color: var(--dim); font-size: 0.72rem; padding-bottom: 0.6rem;
      text-align: center; flex-shrink: 0;
    }
    .meta { display: block; margin-top: 0.55rem; font-size: 0.72rem; color: var(--dim); white-space: normal; }
    .badge { display: inline-block; border-radius: 999px; padding: 0.05rem 0.5rem; margin-right: 0.35rem;
      border: 1px solid var(--line); font-weight: 600; }
    .badge.trade { color: #f0b429; border-color: rgba(240,180,41,0.5); }
    .badge.school { color: var(--acc); border-color: rgba(88,166,255,0.5); }
    .badge.general { color: var(--green); border-color: rgba(63,185,80,0.5); }
    .badge.clarify { color: #d2a8ff; border-color: rgba(210,168,255,0.5); }
    .chip.school { border-style: dashed; }
    .chip.general { border-style: dotted; }
    ::-webkit-scrollbar { width: 8px; }
    ::-webkit-scrollbar-thumb { background: #30363d; border-radius: 4px; }
  </style>
</head>
<body>
  <div class="app">
    <header>
      <div>
        <h1>trade-rag · 全功能助理</h1>
        <p class="sub">本地 Ollama · 多 store FAISS · 交易（只讀）／東吳學校／一般聊天</p>
      </div>
      <div class="status"><span class="dot"></span>本地就緒</div>
    </header>
    <div class="chips">
      <button class="chip" type="button" data-mode="trade" data-q="severe 熱度時新倉預算池是現金多少％？">預算池</button>
      <button class="chip" type="button" data-mode="trade" data-q="硬關跟軟關差在哪？">硬／軟關</button>
      <button class="chip" type="button" data-mode="trade" data-q="今天帳戶跟盤勢怎麼樣？">今日盤勢</button>
      <button class="chip" type="button" data-mode="trade" data-q="夜盤可以進場嗎？">夜盤</button>
      <button class="chip" type="button" data-mode="trade" data-q="個股簡報">個股簡報</button>
      <button class="chip school" type="button" data-q="今天有什麼課？">今天的課</button>
      <button class="chip school" type="button" data-q="選課什麼時候？">選課時段</button>
      <button class="chip school" type="button" data-q="最新公告有哪些？">最新公告</button>
      <button class="chip general" type="button" data-q="用簡單的例子解釋什麼是遞迴">一般問題</button>
    </div>
    <div id="log"></div>
    <div class="composer">
      <textarea id="q" placeholder="問交易、學校或任何問題…（Enter 送出，Shift+Enter 換行）" rows="2"></textarea>
      <button class="send" id="btn" onclick="send()">送出</button>
    </div>
    <div class="foot">不改 Desktop\\trade · 只讀 paper 檔、規則手冊與 scu-backend 資料庫 · <a href="#" id="reset" style="color:inherit">清除對話</a></div>
  </div>
  <script>
  const log = document.getElementById('log');
  const qEl = document.getElementById('q');
  const btn = document.getElementById('btn');

  // 短期記憶：最近幾輪對話（含每則回答的 route，讓路由器能判斷「延續主題」）
  let history = [];
  document.getElementById('reset').addEventListener('click', e => {
    e.preventDefault(); history = []; log.innerHTML = '';
  });
  document.querySelectorAll('.chip').forEach(c => {
    c.addEventListener('click', () => { qEl.value = c.dataset.q; qEl.focus(); send(c.dataset.mode || null); });
  });

  qEl.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
  });

  function esc(s) {
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }
  function renderAnswer(s) {
    const marker = '[[chart:';
    let html = '';
    let rest = String(s);
    while (true) {
      const i = rest.indexOf(marker);
      if (i < 0) { html += esc(rest); break; }
      html += esc(rest.slice(0, i));
      rest = rest.slice(i + marker.length);
      const j = rest.indexOf(']]');
      if (j < 0) { html += esc(marker + rest); break; }
      const url = rest.slice(0, j);
      rest = rest.slice(j + 2);
      if (url.startsWith('/charts/')) {
        html += '<img class="chart" alt="price volume chart" src="' + url + '"/>';
      } else {
        html += esc(marker + url + ']]');
      }
    }
    return html;
  }

  const ROUTE_NAME = {trade: '交易', school: '學校', general: '一般', clarify: '確認'};
  function renderMeta(data) {
    const r = data.route || '';
    let h = `<span class="meta"><span class="badge ${esc(r)}">${esc(ROUTE_NAME[r] || r)}` +
            `${data.sub_route ? ' · ' + esc(data.sub_route) : ''}</span>`;
    const lat = data.latency_ms ? data.latency_ms.total : null;
    if (lat !== null) h += `${(lat/1000).toFixed(1)}s`;
    const d = data.decision || {};
    if (d.stage) h += ` · 判斷：${esc(d.stage)}`;
    const srcs = (data.sources || []).slice(0, 4);
    if (srcs.length) {
      h += '<br/>出處：' + srcs.map(s => {
        const t = esc(s.title || s.source || '');
        return s.url ? `<a href="${esc(s.url)}" target="_blank" style="color:inherit">${t}</a>` : t;
      }).join('；');
    }
    return h + '</span>';
  }

  async function send(mode){
    const q = qEl.value.trim();
    if (!q || btn.disabled) return;
    log.insertAdjacentHTML('beforeend',
      `<div class="bubble q"><span class="who">你</span>${esc(q)}</div>`);
    qEl.value = '';
    btn.disabled = true;
    const pid = 'p' + Date.now();
    log.insertAdjacentHTML('beforeend',
      `<div class="bubble a pending" id="${pid}"><span class="who">助教</span>思考中…</div>`);
    log.scrollTop = log.scrollHeight;
    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({message: q, history: history.slice(-8), mode: mode || undefined})
      });
      const data = await res.json();
      const el = document.getElementById(pid);
      const a = data.answer || data.error || '';
      el.classList.remove('pending');
      if (data.error) el.classList.add('err');
      el.innerHTML = `<span class="who">助教</span>${renderAnswer(a)}${renderMeta(data)}`;
      history.push({role: 'user', content: q});
      history.push({role: 'assistant', content: String(a).slice(0, 1500), route: data.route,
                    clarify: data.clarify || undefined});
      history = history.slice(-12);
    } catch (err) {
      const el = document.getElementById(pid);
      el.classList.remove('pending');
      el.classList.add('err');
      el.innerHTML = `<span class="who">助教</span>${esc(String(err))}`;
    } finally {
      btn.disabled = false;
      log.scrollTop = log.scrollHeight;
      qEl.focus();
    }
  }
  </script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        print("%s - %s" % (self.address_string(), fmt % args))

    def _json(self, obj: dict, status: int = 200) -> None:
        body = json.dumps(obj, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _cors(self) -> None:
        # 入口站是另一個網址（含 file://），瀏覽器要這幾行才叫得到 7861
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:
        if self.path.startswith("/charts/"):
            name = Path(self.path).name
            fp = STATIC_CHARTS / name
            if not fp.exists() or not fp.is_file():
                self.send_error(404)
                return
            data = fp.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)
            return
        if self.path == "/api/health":
            from config import CHAT_MODEL, EMBED_MODEL_NAME, SCU_DB, SCU_DEMO_NOW
            from router import thresholds
            from scu_tools import now
            from stores import discover_stores

            ref = now()
            self._json({"ok": True, "stores": discover_stores(), "chat_model": CHAT_MODEL,
                        "embed_model": EMBED_MODEL_NAME, "scu_db": str(SCU_DB), "scu_db_exists": SCU_DB.is_file(),
                        "demo_now": SCU_DEMO_NOW, "now": ref.isoformat(timespec="minutes"),
                        "router_thresholds": thresholds()})
            return
        if self.path not in ("/", "/index.html"):
            self.send_error(404)
            return
        body = PAGE.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        n = int(self.headers.get("Content-Length", "0") or 0)
        if n > 200_000:
            raise ValueError("request too large")
        raw = self.rfile.read(n) if n else b"{}"
        data = json.loads(raw.decode("utf-8") or "{}")
        if not isinstance(data, dict):
            raise ValueError("JSON body must be an object")
        return data

    def do_POST(self) -> None:
        if self.path == "/api/chat":
            try:
                payload = self._read_json()
                msg = str(payload.get("message") or payload.get("q") or "").strip()
                if not msg:
                    self._json({"error": "empty message"}, 400)
                    return
                history = payload.get("history") or []
                if not isinstance(history, list):
                    history = []
                history = [h for h in history if isinstance(h, dict)][-12:]
                profile = payload.get("profile") if isinstance(payload.get("profile"), dict) else None
                mode = payload.get("mode") if payload.get("mode") in ("trade", "school", "general", "portal") else None
                facts = str(payload.get("facts") or "").strip() or None
                followup = bool(payload.get("followup"))
                out = chat(msg, history, profile, mode, source="api", now=payload.get("now"), facts=facts,
                           followup=followup)
                self._json(out)
            except Exception as e:
                self._json({"error": f"{e}", "trace": traceback.format_exc()[-500:]}, 500)
            return
        if self.path != "/ask":
            self.send_error(404)
            return
        try:
            payload = self._read_json()
            q = str(payload.get("q", "")).strip()
            if not q:
                raise ValueError("empty question")
            result = chat(q, payload.get("history") or None, None, payload.get("mode"), source="ask")
            cites = "\n".join(f"- {s.get('title')}" for s in result.get("sources", [])[:3])
            answer = result["answer"].strip() + (f"\n\n（引用片段）\n{cites}" if cites else "")
            out = {"answer": answer, "route": result.get("route"), "sub_route": result.get("sub_route")}
        except Exception as e:
            out = {"error": f"{e}\n{traceback.format_exc()[-500:]}"}
        self._json(out)


def main() -> None:
    # Windows 主控台可能是 cp950：避免印中文時 UnicodeEncodeError 讓執行緒掛掉
    try:
        import sys

        sys.stdout.reconfigure(errors="replace")
        sys.stderr.reconfigure(errors="replace")
    except Exception:
        pass
    # 先把 embedding 模型與索引載進記憶體，第一個問題就不用等
    try:
        from router import store_sims

        store_sims("暖機")
    except Exception as e:
        print("warmup failed:", e)
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"open http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
