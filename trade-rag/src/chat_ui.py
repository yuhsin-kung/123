"""交易規則助教（標準庫 HTTP，不依賴 Gradio）。

瀏覽器開啟 http://127.0.0.1:7860
"""
from __future__ import annotations

import json
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from pathlib import Path

from answer import ask

ROOT = Path(__file__).resolve().parents[1]
STATIC_CHARTS = ROOT / "static" / "charts"

HOST, PORT = "127.0.0.1", 7860

PAGE = """<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>trade-rag · 規則助教</title>
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
    ::-webkit-scrollbar { width: 8px; }
    ::-webkit-scrollbar-thumb { background: #30363d; border-radius: 4px; }
  </style>
</head>
<body>
  <div class="app">
    <header>
      <div>
        <h1>trade-rag · 規則助教</h1>
        <p class="sub">本地 Ollama · FAISS · 只讀規則／盤勢／帳戶</p>
      </div>
      <div class="status"><span class="dot"></span>本地就緒</div>
    </header>
    <div class="chips">
      <button class="chip" type="button" data-q="severe 熱度時新倉預算池是現金多少％？">預算池</button>
      <button class="chip" type="button" data-q="硬關跟軟關差在哪？">硬／軟關</button>
      <button class="chip" type="button" data-q="今天帳戶跟盤勢怎麼樣？">今日盤勢</button>
      <button class="chip" type="button" data-q="夜盤可以進場嗎？">夜盤</button>
      <button class="chip" type="button" data-q="個股簡報">個股簡報</button>
    </div>
    <div id="log"></div>
    <div class="composer">
      <textarea id="q" placeholder="問規則、盤勢或個股…（Enter 送出，Shift+Enter 換行）" rows="2"></textarea>
      <button class="send" id="btn" onclick="send()">送出</button>
    </div>
    <div class="foot">不改 Desktop\\trade · 只讀 paper 檔與規則手冊</div>
  </div>
  <script>
  const log = document.getElementById('log');
  const qEl = document.getElementById('q');
  const btn = document.getElementById('btn');

  document.querySelectorAll('.chip').forEach(c => {
    c.addEventListener('click', () => { qEl.value = c.dataset.q; qEl.focus(); send(); });
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

  async function send(){
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
      const res = await fetch('/ask', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({q})
      });
      const data = await res.json();
      const el = document.getElementById(pid);
      const a = data.answer || data.error || '';
      el.classList.remove('pending');
      if (data.error) el.classList.add('err');
      el.innerHTML = `<span class="who">助教</span>${renderAnswer(a)}`;
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
        if self.path not in ("/", "/index.html"):
            self.send_error(404)
            return
        body = PAGE.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        if self.path != "/ask":
            self.send_error(404)
            return
        n = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(n)
        try:
            payload = json.loads(raw.decode("utf-8"))
            q = str(payload.get("q", "")).strip()
            if not q:
                raise ValueError("empty question")
            result = ask(q)
            cites = "\n".join(
                f"- {h['source']} / {h['heading']}" for h in result["hits"][:3]
            )
            answer = f"{result['answer'].strip()}\n\n（引用片段）\n{cites}"
            out = {"answer": answer}
        except Exception as e:
            out = {"error": f"{e}\n{traceback.format_exc()[-500:]}"}
        body = json.dumps(out, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"open http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
