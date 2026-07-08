"""
문피아 웹소설 자동 집필기 — 화면(웹) 방식

켜는 법 (맥):
    python3 novel_web.py          # 또는 start_novel_mac.command 더블클릭

- 맥 브라우저:   http://127.0.0.1:5001
- 핸드폰 브라우저: 같은 와이파이에서, 실행 시 표시되는 주소로 접속
  (예: http://192.168.0.10:5001) → 폰에서 바로 원고를 복사해 문피아 앱에 붙여넣기 가능

API 키는 화면에서 입력할 수 있어 환경변수 설정이 필요 없습니다.
"""
from __future__ import annotations

import html
import os
import socket

from flask import Flask, request, redirect

import novel_engine as eng

app = Flask(__name__)

STYLE = """
 body{font-family:"Noto Sans KR","Apple SD Gothic Neo",sans-serif;background:#faf9f6;
   color:#222;margin:0;padding:20px;line-height:1.7}
 .box{max-width:640px;margin:0 auto}
 h1{font-size:22px;margin:0 0 4px} h2{font-size:18px;margin:24px 0 8px}
 .sub{color:#777;font-size:14px;margin-bottom:20px}
 a{color:#7a4dcf;text-decoration:none}
 label{display:block;font-weight:700;margin:16px 0 6px}
 input,textarea{width:100%;padding:12px;border:1px solid #ddd;border-radius:10px;
   font-size:16px;box-sizing:border-box;font-family:inherit}
 textarea{height:80px;resize:vertical}
 button{margin-top:16px;width:100%;padding:15px;border:0;border-radius:12px;
   background:#7a4dcf;color:#fff;font-size:17px;font-weight:800;cursor:pointer}
 button:active{opacity:.85}
 .card{background:#fff;border:1px solid #eee;border-radius:14px;padding:16px;margin:10px 0}
 .card .meta{color:#888;font-size:13px}
 .err{background:#fdecec;color:#b3261e;padding:12px;border-radius:10px;margin:14px 0}
 .hint{color:#999;font-size:12px;margin-top:6px}
 .badge{display:inline-block;background:#f1eafd;color:#7a4dcf;border-radius:8px;
   padding:2px 8px;font-size:12px;margin-right:4px}
 pre.ms{white-space:pre-wrap;background:#fff;border:1px solid #eee;border-radius:14px;
   padding:18px;font-family:inherit;font-size:16px}
 .btn2{display:inline-block;background:#eee;color:#333;border-radius:10px;
   padding:10px 14px;font-weight:700;margin:6px 6px 0 0}
"""


def page(title: str, body: str) -> str:
    return (f'<!doctype html><html lang="ko"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{html.escape(title)}</title><style>{STYLE}</style></head>'
            f'<body><div class="box">{body}</div></body></html>')


def keyfield() -> str:
    if os.getenv("ANTHROPIC_API_KEY"):
        return ""
    return ('<label>Anthropic API 키 *</label>'
            '<input name="api_key" placeholder="sk-ant-..." required>'
            '<div class="hint">console.anthropic.com 에서 발급. 이 컴퓨터 안에서만 사용됩니다.</div>')


def get_key() -> str | None:
    key = (request.form.get("api_key") or "").strip()
    if key:
        os.environ["ANTHROPIC_API_KEY"] = key  # 한 번 넣으면 이 실행 동안 유지
        return key
    return os.getenv("ANTHROPIC_API_KEY")


@app.get("/")
def index():
    err = request.args.get("err", "")
    items = ""
    for p in eng.list_projects():
        items += (f'<div class="card"><a href="/p/{p["slug"]}"><b>「{html.escape(p["title"])}」</b></a>'
                  f'<div class="meta">{p["episodes"]}화까지 집필됨 · {p["slug"]}</div></div>')
    if not items:
        items = '<div class="card"><div class="meta">아직 작품이 없어요. 아래에서 첫 작품을 만들어 보세요!</div></div>'
    body = f"""
     <h1>📚 문피아 웹소설 자동 집필기</h1>
     <div class="sub">소재 한 줄 → 작품 기획 → 버튼 누를 때마다 다음 화 자동 집필 (현대판타지)</div>
     {'<div class="err">⚠️ ' + html.escape(err) + '</div>' if err else ''}
     <h2>내 작품</h2>
     {items}
     <h2>새 작품 만들기</h2>
     <form method="post" action="/new">
      <label>소재 / 컨셉 한 줄 *</label>
      <textarea name="concept" placeholder="예: 만년 F급 헌터가 10년 전으로 회귀. 미래 지식으로 남들보다 먼저 던전을 선점한다" required></textarea>
      {keyfield()}
      <button>✨ 작품 기획하기 (1~2분 소요)</button>
      <div class="hint">제목·시놉시스·주인공·세계관·30화 전개 계획을 자동으로 설계합니다.</div>
     </form>
    """
    return page("문피아 웹소설 자동 집필기", body)


@app.post("/new")
def new_project():
    concept = (request.form.get("concept") or "").strip()
    key = get_key()
    if not concept:
        return redirect("/?err=소재를 입력해 주세요.")
    if not key:
        return redirect("/?err=API 키를 입력해 주세요.")
    try:
        slug = eng.create_project(concept, api_key=key)
    except Exception as e:  # 화면에 원인 표시
        return redirect(f"/?err=작품 기획 중 오류: {e}")
    return redirect(f"/p/{slug}")


@app.get("/p/<slug>")
def project(slug: str):
    try:
        bible = eng.load_bible(slug)
    except FileNotFoundError:
        return redirect("/?err=작품을 찾을 수 없어요.")
    err = request.args.get("err", "")
    n = eng.episode_count(slug)
    tags = "".join(f'<span class="badge">{html.escape(t)}</span>' for t in bible.get("genre_tags", []))
    eps = ""
    for i in range(n, 0, -1):
        ep = eng.load_episode(slug, i)
        eps += (f'<div class="card"><a href="/p/{slug}/ep/{i}"><b>{i}화. {html.escape(ep["title"])}</b></a>'
                f'<div class="meta">공백 포함 {ep.get("chars", len(ep["content"])):,}자</div></div>')
    if not eps:
        eps = '<div class="card"><div class="meta">아직 집필된 회차가 없어요.</div></div>'
    body = f"""
     <div><a href="/">← 작품 목록</a></div>
     <h1>「{html.escape(bible["title"])}」</h1>
     <div class="sub">{tags}</div>
     {'<div class="err">⚠️ ' + html.escape(err) + '</div>' if err else ''}
     <div class="card"><b>한 줄 소개</b><br>{html.escape(bible["logline"])}<br><br>
       <b>시놉시스</b><br>{html.escape(bible["synopsis"]).replace(chr(10), "<br>")}</div>
     <h2>✍️ {n + 1}화 쓰기</h2>
     <form method="post" action="/p/{slug}/write">
      <label>이번 화 지시사항 (선택)</label>
      <textarea name="note" placeholder="예: 이번 화에서 라이벌 길드와 처음 충돌하게 해줘 (비워두면 전개 계획대로 진행)"></textarea>
      {keyfield()}
      <button>✍️ {n + 1}화 자동 집필 (2~5분 소요)</button>
      <div class="hint">버튼을 누른 뒤 원고가 완성될 때까지 창을 닫지 말고 기다려 주세요.</div>
     </form>
     <h2>회차 목록</h2>
     {eps}
    """
    return page(bible["title"], body)


@app.post("/p/<slug>/write")
def write(slug: str):
    key = get_key()
    if not key:
        return redirect(f"/p/{slug}?err=API 키를 입력해 주세요.")
    note = (request.form.get("note") or "").strip()
    try:
        ep = eng.write_next_episode(slug, instructions=note, api_key=key)
    except Exception as e:
        return redirect(f"/p/{slug}?err=집필 중 오류: {e}")
    return redirect(f"/p/{slug}/ep/{ep['number']}")


@app.get("/p/<slug>/ep/<int:num>")
def episode(slug: str, num: int):
    try:
        bible = eng.load_bible(slug)
        ep = eng.load_episode(slug, num)
    except FileNotFoundError:
        return redirect(f"/p/{slug}?err=회차를 찾을 수 없어요.")
    manuscript = f"{num}화. {ep['title']}\n\n{ep['content']}"
    body = f"""
     <div><a href="/p/{slug}">← 「{html.escape(bible["title"])}」</a></div>
     <h1>{num}화. {html.escape(ep["title"])}</h1>
     <div class="sub">공백 포함 {ep.get("chars", len(ep["content"])):,}자 ·
       복사해서 문피아 회차 등록에 붙여넣으세요</div>
     <button onclick="copyMs()" style="margin-top:0">📋 원고 전체 복사</button>
     <div id="ok" class="hint"></div>
     <pre class="ms" id="ms">{html.escape(manuscript)}</pre>
    <script>
    function copyMs(){{
      navigator.clipboard.writeText(document.getElementById('ms').innerText).then(
        () => document.getElementById('ok').innerText = '✅ 복사됐어요! 문피아에 붙여넣으세요.',
        () => document.getElementById('ok').innerText = '복사 실패 — 본문을 길게 눌러 직접 복사해 주세요.');
    }}
    </script>
    """
    return page(f"{num}화. {ep['title']}", body)


def _local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"


if __name__ == "__main__":
    ip = _local_ip()
    print("\n  ── 문피아 웹소설 자동 집필기 ──")
    print("  맥에서:      http://127.0.0.1:5001")
    print(f"  핸드폰에서:  http://{ip}:5001  (같은 와이파이에 연결돼 있어야 해요)")
    print("  종료: 이 창에서 Ctrl+C\n")
    app.run(host="0.0.0.0", port=5001, debug=False)
