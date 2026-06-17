"""
AI가 만든 글 구조를 -> 실제 블로그처럼 보이는 HTML 파일로 바꾸고,
사진 자리에 넣을 '플레이스홀더 이미지'를 만든다.

색상은 밝은 배경, 폰트/크기는 상위 1% 블로거 형식(seo_rules.py)을 그대로 적용.
"""
from __future__ import annotations

import html
import os
import re

# 직접 찍은 사진을 넣기 전, 미리보기용 임시 이미지를 만들 때 사용
try:
    from PIL import Image, ImageDraw, ImageFont
    _PIL_OK = True
except ImportError:
    _PIL_OK = False


# ── 밝은 배경 + 상위 1% 형식 폰트/크기 (seo_rules.py 사양과 일치) ──
CSS = """
:root { --ink:#222; --soft:#555; --accent:#1a7f5a; --bg:#fffdf8; --line:#eee; }
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--ink);
  font-family: "Noto Sans KR","나눔고딕","Apple SD Gothic Neo",sans-serif;
  font-size: 16px; line-height: 1.8; -webkit-text-size-adjust: 100%;
}
.post { max-width: 720px; margin: 0 auto; padding: 28px 20px 80px; }
h1 { font-size: 28px; line-height: 1.45; font-weight: 800; margin: 8px 0 6px; }
.meta { color: var(--soft); font-size: 13px; margin-bottom: 24px; }
h2 {
  font-size: 21px; font-weight: 800; margin: 40px 0 12px;
  padding-left: 12px; border-left: 5px solid var(--accent); line-height: 1.4;
}
p { margin: 0 0 16px; }
.lead { font-size: 17px; color: var(--ink); }
figure { margin: 22px 0; }
figure img { width: 100%; border-radius: 12px; display: block; }
figcaption { color: var(--soft); font-size: 13px; text-align: center; margin-top: 8px; }
.guide {
  background: #f4f9f6; border: 1px dashed var(--accent); border-radius: 10px;
  padding: 10px 14px; font-size: 13px; color: var(--accent); margin-top: 8px;
}
.tags { margin-top: 40px; padding-top: 20px; border-top: 1px solid var(--line); }
.tag {
  display: inline-block; background: #eef5f1; color: var(--accent);
  border-radius: 999px; padding: 5px 12px; margin: 0 6px 8px 0; font-size: 13px;
}
.tip { color: var(--soft); font-size: 13px; margin-top: 30px; }
strong { color: #111; }
"""


def _slug(text: str) -> str:
    """파일 이름에 쓰기 안전한 짧은 문자열로 변환."""
    text = re.sub(r"[^\w가-힣]+", "-", text).strip("-")
    return (text[:40] or "post").lower()


def make_placeholder_image(path: str, caption: str, index: int) -> None:
    """직접 찍은 사진을 넣기 전, '여기에 사진' 임시 이미지를 만든다."""
    if not _PIL_OK:
        return
    w, h = 1080, 720
    palette = ["#cfe8dc", "#d7e3f4", "#f4e3cf", "#e8d7e3", "#dce8cf"]
    img = Image.new("RGB", (w, h), palette[index % len(palette)])
    draw = ImageDraw.Draw(img)

    korean_font = None  # 한글 렌더링 가능한 폰트 경로
    for p in ("/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
              "/System/Library/Fonts/AppleSDGothicNeo.ttc",
              "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"):
        if os.path.exists(p):
            korean_font = p
            break

    def font(size: int):
        for p in (korean_font, "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
            if p and os.path.exists(p):
                try:
                    return ImageFont.truetype(p, size)
                except OSError:
                    pass
        return ImageFont.load_default()

    # 한글 폰트가 없으면 글자가 깨지므로 영문으로 안내
    if korean_font:
        title_txt = f"사진 {index + 1}"
        cap_lines, line = [], ""
        for ch in caption:
            line += ch
            if len(line) >= 18:
                cap_lines.append(line); line = ""
        if line:
            cap_lines.append(line)
    else:
        title_txt = f"PHOTO {index + 1}"
        cap_lines = ["replace with", "your own photo"]

    draw.text((w // 2, h // 2 - 40), title_txt, font=font(64),
              fill="#33493f", anchor="mm")
    for i, ln in enumerate(cap_lines[:3]):
        draw.text((w // 2, h // 2 + 30 + i * 38), ln, font=font(30),
                  fill="#33493f", anchor="mm")
    img.save(path, "JPEG", quality=85)


def render(post: dict, outdir: str) -> str:
    """글 구조(dict)를 HTML 파일로 저장하고, 사진 임시 이미지를 만든다. 경로 반환."""
    os.makedirs(outdir, exist_ok=True)
    img_dir = os.path.join(outdir, "images")
    os.makedirs(img_dir, exist_ok=True)

    title = post["title"]
    parts: list[str] = []
    parts.append(f"<h1>{html.escape(title)}</h1>")
    kw = ", ".join(post.get("keywords", []))
    parts.append(f'<p class="meta">대표 키워드: {html.escape(kw)} · '
                 f'직접 찍은 사진을 넣고 발행하세요</p>')
    parts.append(f'<p class="lead">{html.escape(post["intro"])}</p>')

    img_count = 0
    for sec in post["sections"]:
        parts.append(f"<h2>{html.escape(sec['heading'])}</h2>")
        for para in sec["paragraphs"]:
            parts.append(f"<p>{html.escape(para)}</p>")
        slot = sec.get("image")
        if slot:
            fname = f"image_{img_count + 1}.jpg"
            make_placeholder_image(os.path.join(img_dir, fname),
                                   slot["caption"], img_count)
            parts.append(
                f'<figure><img src="images/{fname}" alt="{html.escape(slot["caption"])}">'
                f'<figcaption>{html.escape(slot["caption"])}</figcaption>'
                f'<div class="guide">📸 직접 찍을 사진 가이드: '
                f'{html.escape(slot["photo_guide"])}</div></figure>'
            )
            img_count += 1

    parts.append(f"<h2>마무리</h2><p>{html.escape(post['conclusion'])}</p>")

    if post.get("tags"):
        chips = "".join(f'<span class="tag">#{html.escape(t)}</span>'
                        for t in post["tags"])
        parts.append(f'<div class="tags">{chips}</div>')

    parts.append('<p class="tip">※ 이 임시 사진들을 <b>직접 찍은 원본 사진</b>으로 '
                 '교체하면 네이버 상위노출 점수가 크게 올라갑니다 (2026년 규칙).</p>')

    body = "\n".join(parts)
    doc = (f"<!doctype html><html lang='ko'><head><meta charset='utf-8'>"
           f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
           f"<title>{html.escape(title)}</title><style>{CSS}</style></head>"
           f"<body><article class='post'>{body}</article></body></html>")

    out_path = os.path.join(outdir, f"{_slug(title)}.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(doc)
    return out_path
