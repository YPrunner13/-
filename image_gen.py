"""
AI 이미지 생성 모듈.

Claude는 글만 쓰고 그림은 못 만들기 때문에, 외부 이미지 생성 서비스를 사용한다.

두 가지 방식을 지원:
  1) Pollinations.ai  — 무료, 가입·API 키 불필요 (기본값)
  2) OpenAI gpt-image-1 — 고품질, OPENAI_API_KEY 가 있으면 자동으로 이쪽 사용

둘 다 실패하면 False를 돌려주고, 호출한 쪽에서 임시 이미지로 대체한다.
"""
from __future__ import annotations

import base64
import os
import urllib.parse
import urllib.request


def _gen_openai(prompt: str, path: str) -> bool:
    """OpenAI gpt-image-1 로 이미지 생성. 성공 시 True."""
    try:
        from openai import OpenAI  # 키가 있을 때만 필요 (지연 임포트)
    except ImportError:
        print("   (OpenAI 키는 있으나 openai 패키지 미설치 → 무료 방식으로 진행)")
        return False
    try:
        client = OpenAI()
        result = client.images.generate(
            model="gpt-image-1", prompt=prompt, size="1536x1024"
        )
        data = base64.b64decode(result.data[0].b64_json)
        with open(path, "wb") as f:
            f.write(data)
        return True
    except Exception as e:  # 네트워크/쿼터/키 오류 등
        print(f"   (OpenAI 이미지 생성 실패: {e} → 무료 방식으로 진행)")
        return False


def _gen_pollinations(prompt: str, path: str, seed: int) -> bool:
    """Pollinations.ai 로 이미지 생성(무료·무가입). 성공 시 True."""
    enc = urllib.parse.quote(prompt)
    url = (f"https://image.pollinations.ai/prompt/{enc}"
           f"?width=1080&height=720&model=flux&nologo=true&seed={seed}")
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (blog-writer)",
                     "Referer": "https://pollinations.ai/"},
        )
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = resp.read()
        if not data or len(data) < 1000:  # 너무 작으면 실패로 간주
            return False
        with open(path, "wb") as f:
            f.write(data)
        return True
    except Exception as e:
        print(f"   (무료 이미지 생성 실패: {e} → 임시 이미지로 대체)")
        return False


def generate_image(prompt: str, path: str, seed: int = 0) -> bool:
    """프롬프트로 이미지를 만들어 path에 저장. 성공하면 True.

    OPENAI_API_KEY 가 있으면 OpenAI 먼저 시도하고, 없거나 실패하면 무료 방식 사용.
    """
    if not prompt.strip():
        return False
    if os.getenv("OPENAI_API_KEY"):
        if _gen_openai(prompt, path):
            return True
    return _gen_pollinations(prompt, path, seed)
