"""
네이버 블로그 글 자동 작성기 (2026년 6월 SEO 규칙 적용)

사용법:
    python main.py "주제나 키워드" --notes "내가 직접 겪은 경험 메모"

예:
    python main.py "성수동 카페 추천" --notes "친구랑 토요일 오후 방문, 아메리카노 5500원, 웨이팅 20분"

결과:
    output/ 폴더에 블로그 HTML 한 개 + 사진 자리 임시 이미지가 생성됩니다.
    HTML을 브라우저로 열어보고, 글을 복사해 네이버 블로그에 붙여넣은 뒤
    임시 사진을 '직접 찍은 사진'으로 바꿔 발행하면 됩니다.

준비물:
    환경변수 ANTHROPIC_API_KEY 에 Anthropic API 키만 있으면 됩니다.
    (네이버 로그인·가입 불필요. 글은 내가 직접 붙여넣고 발행합니다.)
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import List

import anthropic
from pydantic import BaseModel, Field

from render import render
from seo_rules import build_system_prompt

MODEL = "claude-opus-4-8"


# ── AI가 채워줄 글의 '뼈대' (구조화 출력 스키마) ──
class ImageSlot(BaseModel):
    caption: str = Field(description="사진 아래 들어갈 짧은 설명(캡션)")
    photo_guide: str = Field(description="독자가 직접 어떤 사진을 찍어 넣으면 좋을지 구체적 가이드")
    image_prompt: str = Field(
        description="이 사진을 AI로 생성하기 위한 영어 프롬프트. "
        "photorealistic, natural lighting 같은 사실적 사진 묘사로 작성")


class Section(BaseModel):
    heading: str = Field(description="소제목(H2). 가능하면 검색의도를 담은 질문형")
    paragraphs: List[str] = Field(description="2~3줄짜리 짧은 문단 2~4개")
    image: ImageSlot = Field(description="이 단락에 들어갈 사진 자리")


class BlogPost(BaseModel):
    title: str = Field(description="대표 키워드를 앞쪽에 넣은, 클릭하고 싶은 제목")
    keywords: List[str] = Field(description="대표 키워드 1개 + 연관 키워드 2~3개")
    intro: str = Field(description="검색의도를 바로 짚어주는 후킹 도입부 (3~4문장)")
    sections: List[Section] = Field(description="소제목 단락 5~6개 (각각 사진 1장 = 사진 5장 이상 확보)")
    conclusion: str = Field(description="솔직한 총평 + 한 줄 요약 마무리")
    tags: List[str] = Field(description="네이버 태그 8~10개")


def generate(topic: str, notes: str, api_key: str | None = None) -> dict:
    """Claude(claude-opus-4-8)로 2026 SEO 규칙에 맞는 블로그 글 구조를 생성한다.

    api_key 를 주면 그 키로, 없으면 환경변수 ANTHROPIC_API_KEY 를 사용한다.
    """
    client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()

    user_msg = (
        f"아래 주제로 네이버 블로그 글을 작성해 주세요.\n\n"
        f"[주제/키워드]\n{topic}\n\n"
        f"[내가 직접 겪은 경험 메모]\n{notes or '(메모 없음 — 일반적이되 경험한 것처럼 구체적으로 작성)'}\n\n"
        f"요구사항:\n"
        f"- 위 경험 메모의 구체적 수치(가격/시간/날짜 등)를 본문에 자연스럽게 녹일 것\n"
        f"- 소제목은 검색하는 사람이 궁금해할 질문 위주로\n"
        f"- 사진 자리는 5장 이상, 각 자리에 '직접 찍을 사진 가이드'를 구체적으로\n"
        f"- 키워드 반복·글자수 채우기 금지, 진짜 경험한 사람의 말투로"
    )

    resp = client.messages.parse(
        model=MODEL,
        max_tokens=16000,
        thinking={"type": "adaptive"},
        system=build_system_prompt(),
        messages=[{"role": "user", "content": user_msg}],
        output_format=BlogPost,
    )
    post = resp.parsed_output
    if post is None:
        raise RuntimeError("글 생성에 실패했습니다. 다시 시도해 주세요.")
    return post.model_dump()


def main() -> None:
    parser = argparse.ArgumentParser(description="네이버 블로그 글 자동 작성기 (2026 SEO)")
    parser.add_argument("topic", help="글 주제 또는 키워드")
    parser.add_argument("--notes", default="", help="직접 겪은 경험 메모(있으면 점수 상승)")
    parser.add_argument("--out", default="output", help="결과를 저장할 폴더 (기본: output)")
    parser.add_argument("--no-ai-images", action="store_true",
                        help="AI 이미지 생성을 끄고 빈 사진 자리(임시 이미지)만 만든다")
    args = parser.parse_args()

    if not os.getenv("ANTHROPIC_API_KEY"):
        print("⚠️  환경변수 ANTHROPIC_API_KEY 가 없습니다.\n"
              "   터미널에서 다음을 먼저 실행하세요:\n"
              "   export ANTHROPIC_API_KEY='발급받은_키'", file=sys.stderr)
        sys.exit(1)

    print(f"✍️  '{args.topic}' 주제로 2026 SEO 규칙에 맞춰 글을 작성 중...")
    post = generate(args.topic, args.notes)

    use_ai = not args.no_ai_images
    if use_ai:
        src = "OpenAI(고품질)" if os.getenv("OPENAI_API_KEY") else "Pollinations(무료)"
        print(f"🖼️  AI 이미지 생성 중... ({src})")
    path = render(post, args.out, use_ai_images=use_ai)

    print("\n✅ 완성!")
    print(f"   - 제목: {post['title']}")
    print(f"   - 소제목 {len(post['sections'])}개, 사진 자리 {len(post['sections'])}장")
    print(f"   - 파일: {path}")
    print("\n다음 단계:")
    print("   1) 위 HTML 파일을 브라우저로 열어 글을 확인")
    print("   2) 글을 복사해 네이버 블로그 글쓰기에 붙여넣기")
    print("   3) 임시 사진을 '직접 찍은 사진'으로 교체 후 발행 (상위노출 핵심!)")


if __name__ == "__main__":
    main()
