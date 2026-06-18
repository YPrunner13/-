"""
화면(웹) 방식 실행기 — 터미널 명령어 없이 브라우저에서 클릭만으로 글을 만든다.

켜는 법:
    python web_app.py
실행 후 브라우저에서 http://127.0.0.1:5000 접속.
주제를 입력하고 버튼을 누르면 글과 사진이 만들어지고, 바로 미리보기로 보여준다.

API 키는 화면에서 입력할 수 있어 환경변수 설정이 필요 없다.
(환경변수 ANTHROPIC_API_KEY 가 이미 있으면 입력칸은 비워둬도 됨)
"""
from __future__ import annotations

import os
import time

from flask import Flask, request, send_from_directory

from main import generate
from render import render

app = Flask(__name__)
WEBOUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "webout")
os.makedirs(WEBOUT, exist_ok=True)

PAGE = """<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>네이버 블로그 글 자동 작성기</title>
<style>
 body{{font-family:"Noto Sans KR",sans-serif;background:#fffdf8;color:#222;
   margin:0;padding:24px;line-height:1.7}}
 .box{{max-width:640px;margin:0 auto}}
 h1{{font-size:24px;margin:0 0 4px}}
 .sub{{color:#777;font-size:14px;margin-bottom:24px}}
 label{{display:block;font-weight:700;margin:18px 0 6px}}
 input,textarea{{width:100%;padding:12px;border:1px solid #ddd;border-radius:10px;
   font-size:16px;box-sizing:border-box;font-family:inherit}}
 textarea{{height:90px;resize:vertical}}
 .row{{display:flex;align-items:center;gap:8px;margin-top:14px;color:#555;font-size:14px}}
 button{{margin-top:22px;width:100%;padding:15px;border:0;border-radius:12px;
   background:#1a7f5a;color:#fff;font-size:17px;font-weight:800;cursor:pointer}}
 button:active{{opacity:.85}}
 .hint{{color:#999;font-size:12px;margin-top:6px}}
 .err{{background:#fdecec;color:#b3261e;padding:12px;border-radius:10px;margin-bottom:16px}}
 details{{margin-top:14px}} summary{{cursor:pointer;color:#1a7f5a;font-size:14px}}
</style></head><body><div class="box">
 <h1>📝 네이버 블로그 글 자동 작성기</h1>
 <div class="sub">주제만 넣으면 2026 SEO 규칙에 맞춰 글+사진을 만들어 드려요.</div>
 {error}
 <form method="post" action="/generate">
  <label>글 주제 *</label>
  <input name="topic" placeholder="예: 성수동 카페 추천" required value="{topic}">
  <label>직접 겪은 경험 메모 (선택, 있으면 점수↑)</label>
  <textarea name="notes" placeholder="예: 토요일 오후 방문, 아메리카노 5500원, 웨이팅 20분">{notes}</textarea>
  {keyfield}
  <details><summary>고품질 사진 옵션 (선택)</summary>
   <label>OpenAI API 키 (넣으면 고품질 사진, 비우면 무료 사진)</label>
   <input name="openai_key" placeholder="sk-... (없으면 비워두세요)">
  </details>
  <div class="row"><input type="checkbox" name="ai_images" checked style="width:auto">
   AI로 사진도 같이 생성</div>
  <button>✨ 글 만들기 (30초~2분 소요)</button>
  <div class="hint">버튼을 누른 뒤 글이 완성될 때까지 잠시 기다려 주세요.</div>
 </form>
</div></body></html>"""

RESULT = """<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>완성!</title>
<style>
 body{{font-family:"Noto Sans KR",sans-serif;background:#fffdf8;margin:0;padding:20px;color:#222}}
 .bar{{max-width:760px;margin:0 auto 16px}}
 h1{{font-size:20px}} a.btn,button{{display:inline-block;background:#1a7f5a;color:#fff;
   text-decoration:none;padding:11px 16px;border-radius:10px;font-weight:700;border:0;
   font-size:15px;cursor:pointer;margin:4px 6px 4px 0}}
 a.ghost{{background:#eef5f1;color:#1a7f5a}}
 iframe{{width:100%;max-width:760px;height:75vh;border:1px solid #e5e5e5;border-radius:12px;
   display:block;margin:0 auto;background:#fff}}
 .tip{{max-width:760px;margin:14px auto;color:#666;font-size:14px}}
</style></head><body>
 <div class="bar"><h1>✅ 완성됐어요!</h1>
  <a class="btn" href="/files/{run}/{html}" target="_blank">📄 전체 글 새 탭에서 열기</a>
  <a class="btn ghost" href="/">← 다른 글 만들기</a>
 </div>
 <iframe src="/files/{run}/{html}"></iframe>
 <div class="tip">위 글을 새 탭에서 열고 → 전체 선택(Ctrl/⌘+A) → 복사 →
  <b>네이버 블로그 글쓰기</b>에 붙여넣으세요. 사진은 가능하면 직접 찍은 사진으로 바꿔 발행하면 좋아요.</div>
</body></html>"""


def form(error: str = "", topic: str = "", notes: str = "") -> str:
    # 환경변수에 키가 이미 있으면 키 입력칸을 숨긴다
    keyfield = ""
    if not os.getenv("ANTHROPIC_API_KEY"):
        keyfield = ('<label>Anthropic API 키 *</label>'
                    '<input name="api_key" placeholder="sk-ant-..." required>'
                    '<div class="hint">console.anthropic.com 에서 발급. '
                    '입력값은 이 컴퓨터 안에서만 사용됩니다.</div>')
    err = f'<div class="err">⚠️ {error}</div>' if error else ""
    return PAGE.format(error=err, topic=topic, notes=notes, keyfield=keyfield)


@app.get("/")
def index():
    return form()


@app.post("/generate")
def do_generate():
    topic = (request.form.get("topic") or "").strip()
    notes = (request.form.get("notes") or "").strip()
    api_key = (request.form.get("api_key") or "").strip() or os.getenv("ANTHROPIC_API_KEY")
    openai_key = (request.form.get("openai_key") or "").strip()
    use_ai = request.form.get("ai_images") == "on"

    if not topic:
        return form("주제를 입력해 주세요.")
    if not api_key:
        return form("Anthropic API 키를 입력해 주세요.")

    # 이미지 고품질용 OpenAI 키가 입력되면 이번 실행에만 적용
    if openai_key:
        os.environ["OPENAI_API_KEY"] = openai_key

    run = f"run_{int(time.time())}"
    outdir = os.path.join(WEBOUT, run)
    try:
        post = generate(topic, notes, api_key=api_key)
        path = render(post, outdir, use_ai_images=use_ai)
    except Exception as e:
        return form(f"글 생성 중 오류가 났어요: {e}", topic, notes)

    return RESULT.format(run=run, html=os.path.basename(path))


@app.get("/files/<run>/<path:filename>")
def files(run: str, filename: str):
    # 생성된 글/이미지를 브라우저에 보여주기 위해 제공
    return send_from_directory(os.path.join(WEBOUT, run), filename)


if __name__ == "__main__":
    print("\n  브라우저에서 다음 주소로 접속하세요:  http://127.0.0.1:5000\n"
          "  (종료하려면 이 창에서 Ctrl+C)\n")
    app.run(host="127.0.0.1", port=5000, debug=False)
