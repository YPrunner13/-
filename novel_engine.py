"""
문피아 현대판타지 웹소설 자동 집필기 — 핵심 엔진

사용법(터미널):
    # 1) 새 작품 기획 (소재 한 줄이면 됩니다)
    python novel_engine.py new "회귀한 재벌집 경호원이 헌터가 되는 이야기"

    # 2) 다음 화 집필 (몇 번이고 반복하면 1화, 2화, 3화... 이어서 씁니다)
    python novel_engine.py write work_20260708_120000

터미널이 어려우면 novel_web.py (화면 방식)를 쓰세요.

결과:
    novel_projects/<작품폴더>/ 안에
    - bible.json          작품 설정집 (제목/시놉시스/주인공/세계관/전개 계획)
    - episodes/epNNN.txt  문피아에 바로 붙여넣을 수 있는 회차 원고
    - episodes/epNNN.json 회차 데이터 (요약 포함 — 다음 화 이어쓰기에 사용)

준비물:
    환경변수 ANTHROPIC_API_KEY (웹 화면에서는 입력칸으로 대체 가능)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from typing import List

import anthropic
from pydantic import BaseModel, Field

MODEL = "claude-opus-4-8"
PROJECTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "novel_projects")

# 문피아 현대판타지 한 화 기준 분량 (공백 포함 글자 수)
MIN_CHARS = 5000
MAX_CHARS = 5600


# ─────────────────────────── 작품 설정집(바이블) 스키마 ───────────────────────────
class Character(BaseModel):
    name: str = Field(description="이름")
    role: str = Field(description="역할 (주인공/조력자/라이벌/빌런 등)")
    profile: str = Field(description="나이, 배경, 성격, 능력, 서사적 역할을 3~5문장으로")


class StoryBible(BaseModel):
    title: str = Field(description="문피아 스타일 제목. 클릭을 부르는 직관적 제목 "
                       "(예: 'SSS급 헌터로 회귀했다', '재벌집 막내 경호원')")
    genre_tags: List[str] = Field(description="장르 태그 4~6개 (예: 현대판타지, 회귀, 헌터, 성장)")
    logline: str = Field(description="한 줄 소개 (문피아 작품 소개 첫 줄용)")
    synopsis: str = Field(description="작품 소개란에 넣을 시놉시스 5~8문장. 스포일러 없이 후킹 위주")
    protagonist: Character = Field(description="주인공. 확실한 치트/강점과 명확한 목표가 있어야 함")
    characters: List[Character] = Field(description="주요 조연·라이벌·빌런 3~5명")
    world_rules: str = Field(description="세계관과 파워 시스템 규칙 (상태창/게이트/각성 체계 등)을 "
                             "구체적으로. 회차 집필 시 설정 붕괴가 없도록 수치·등급 체계까지")
    style_guide: str = Field(description="문체 가이드: 시점(1인칭/3인칭), 톤, 대사 비중, 전개 속도")
    arc_plan: List[str] = Field(description="1부(약 25~30화)의 상세 전개 계획을 화수 구간별로 8~12줄. "
                                "각 줄은 '1~3화: ...' 형식")
    long_term_plan: List[str] = Field(description="300화 이상 장기 연재 로드맵을 부(部) 단위로 5~8줄. "
                                      "각 줄은 '1부(1~30화): ...' 형식. 특정 악역 하나를 쫓는 구조가 아니라 "
                                      "주인공이 더 큰 무대로 올라갈수록 상대가 자연히 커지는 확장 구조로. "
                                      "각 부마다 명확한 목표와 마무리가 있어야 함")


# ─────────────────────────── 회차 출력 스키마 (구조화 출력) ───────────────────────────
EPISODE_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {
            "type": "string",
            "description": "이 화의 소제목 (화수 없이 소제목만, 예: '각성')",
        },
        "content": {
            "type": "string",
            "description": f"회차 본문 전체. 공백 포함 {MIN_CHARS}~{MAX_CHARS}자. "
                           "문단 사이는 빈 줄로 구분",
        },
        "summary": {
            "type": "string",
            "description": "이 화에서 벌어진 사건·설정 변화·복선을 다음 화 집필자가 참고할 수 있게 "
                           "5~8문장으로 요약",
        },
        "next_hook": {
            "type": "string",
            "description": "다음 화 도입 방향 메모 2~3문장 (절단신공을 어떻게 받아서 시작할지)",
        },
    },
    "required": ["title", "content", "summary", "next_hook"],
    "additionalProperties": False,
}


# ─────────────────────────── 프롬프트 ───────────────────────────
def _bible_system_prompt() -> str:
    return (
        "당신은 문피아에서 유료 연재 중인 베테랑 현대판타지 웹소설 작가이자 기획자다.\n"
        "요즘 문피아 독자들이 좋아하는 흥행 공식을 정확히 알고 있다:\n"
        "- 주인공에게 확실한 치트(회귀 지식, 시스템, 유일 능력 등)와 명확한 단기 목표\n"
        "- 사이다 전개, 고구마 최소화, 빠른 성장과 보상\n"
        "- 1~5화 안에 주인공의 특별함이 드러나는 구조\n"
        "- 설정 붕괴가 없도록 수치화된 파워 시스템\n"
        "주어진 소재로 장기 연재가 가능한 탄탄한 작품 설정집을 만들어라."
    )


def _episode_system_prompt(bible: dict) -> str:
    return (
        "당신은 문피아에서 유료 연재 중인 베테랑 현대판타지 웹소설 작가다.\n"
        "아래 작품 설정집을 절대 어기지 말고, 요청받은 화를 집필하라.\n\n"
        f"[작품 설정집]\n{json.dumps(bible, ensure_ascii=False, indent=1)}\n\n"
        "[문피아 연재 원칙 — 반드시 지킬 것]\n"
        f"1. 분량: 공백 포함 {MIN_CHARS}~{MAX_CHARS}자. 절대 {MIN_CHARS}자 미만 금지.\n"
        "2. 모바일 가독성: 문장은 짧게. 한두 문장마다 줄을 바꾸고 문단 사이는 빈 줄.\n"
        "3. 대사 비중을 높게(전체의 40% 이상). 대사는 큰따옴표, 속마음은 작은따옴표.\n"
        "4. 사이다 전개: 답답한 전개를 오래 끌지 않는다. 갈등은 만들되 화 안에서 통쾌한 진전이 있어야 한다.\n"
        "5. 절단신공: 매 화 마지막은 다음 화를 누르지 않고는 못 배기는 지점에서 끊는다.\n"
        "6. 도입 3줄 안에 독자를 붙잡는다. 지난 화 요약이나 설명으로 시작하지 않는다.\n"
        "7. 설정·수치·인물 관계는 설정집과 이전 화 요약에 맞춘다. 새 설정을 함부로 추가하지 않는다.\n"
        "8. 번역투·감탄사 남발·과한 수식어 금지. 요즘 한국 웹소설의 건조하고 속도감 있는 문체로.\n"
        "9. 장기 연재 페이스: arc_plan(1부 상세)과 long_term_plan(전체 로드맵)에서 지금 화수가 속한 "
        "구간의 사건만 다룬다. 전개를 앞당겨 소진하지 말 것. 이 작품은 300화 이상 연재가 목표다."
    )


def _episode_user_prompt(ep_num: int, prev_summaries: List[str],
                         prev_tail: str, instructions: str) -> str:
    parts = [f"이제 {ep_num}화를 집필하라."]
    if ep_num == 1:
        parts.append(
            "1화다. 작품의 첫인상을 결정한다. 주인공의 상황과 치트가 강렬하게 드러나는 "
            "사건으로 시작하고, 세계관 설명은 사건 속에 자연스럽게 녹여라."
        )
    if prev_summaries:
        joined = "\n".join(prev_summaries)
        parts.append(f"[지금까지의 이야기 (화별 요약)]\n{joined}")
    if prev_tail:
        parts.append(
            "[직전 화의 마지막 부분 — 이 장면에서 자연스럽게 이어서 시작하라. "
            "같은 문장을 반복하지 말 것]\n" + prev_tail
        )
    if instructions.strip():
        parts.append(f"[작가(사용자)의 이번 화 지시사항 — 최우선으로 반영]\n{instructions.strip()}")
    parts.append("본문(content)은 완성된 원고여야 한다. 메모나 개요가 아니라 실제 소설 본문을 써라.")
    return "\n\n".join(parts)


# ─────────────────────────── 저장/불러오기 ───────────────────────────
def _client(api_key: str | None) -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()


def list_projects() -> List[dict]:
    """저장된 작품 목록을 [{slug, title, episodes}] 형태로 반환."""
    if not os.path.isdir(PROJECTS_DIR):
        return []
    out = []
    for slug in sorted(os.listdir(PROJECTS_DIR), reverse=True):
        bible_path = os.path.join(PROJECTS_DIR, slug, "bible.json")
        if not os.path.isfile(bible_path):
            continue
        with open(bible_path, encoding="utf-8") as f:
            bible = json.load(f)
        out.append({
            "slug": slug,
            "title": bible.get("title", slug),
            "episodes": episode_count(slug),
        })
    return out


def load_bible(slug: str) -> dict:
    with open(os.path.join(PROJECTS_DIR, slug, "bible.json"), encoding="utf-8") as f:
        return json.load(f)


def episode_count(slug: str) -> int:
    ep_dir = os.path.join(PROJECTS_DIR, slug, "episodes")
    if not os.path.isdir(ep_dir):
        return 0
    return len([f for f in os.listdir(ep_dir) if re.fullmatch(r"ep\d{3}\.json", f)])


def load_episode(slug: str, num: int) -> dict:
    path = os.path.join(PROJECTS_DIR, slug, "episodes", f"ep{num:03d}.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ─────────────────────────── 생성 ───────────────────────────
def create_project(concept: str, api_key: str | None = None) -> str:
    """소재 한 줄로 작품 설정집을 만들고 프로젝트 폴더를 생성. slug를 반환."""
    client = _client(api_key)
    resp = client.messages.parse(
        model=MODEL,
        max_tokens=16000,
        thinking={"type": "adaptive"},
        system=_bible_system_prompt(),
        messages=[{
            "role": "user",
            "content": f"다음 소재로 문피아 연재용 현대판타지 작품 설정집을 만들어 주세요.\n\n[소재]\n{concept}",
        }],
        output_format=StoryBible,
    )
    bible = resp.parsed_output
    if bible is None:
        raise RuntimeError("작품 기획 생성에 실패했습니다. 다시 시도해 주세요.")

    slug = time.strftime("work_%Y%m%d_%H%M%S")
    proj = os.path.join(PROJECTS_DIR, slug)
    os.makedirs(os.path.join(proj, "episodes"), exist_ok=True)
    data = bible.model_dump()
    data["_concept"] = concept
    with open(os.path.join(proj, "bible.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return slug


def write_next_episode(slug: str, instructions: str = "",
                       api_key: str | None = None,
                       on_progress=None) -> dict:
    """다음 화를 집필해 저장하고 회차 데이터를 반환.

    on_progress(글자수) 콜백을 주면 생성 중간중간 진행 상황을 알 수 있다.
    """
    bible = load_bible(slug)
    ep_num = episode_count(slug) + 1

    # 이전 화들의 요약 + 직전 화 끝부분(이어쓰기용)
    prev_summaries: List[str] = []
    prev_tail = ""
    for n in range(1, ep_num):
        ep = load_episode(slug, n)
        prev_summaries.append(f"{n}화 「{ep['title']}」: {ep['summary']}")
        if n == ep_num - 1:
            prev_tail = ep["content"][-800:]
            if ep.get("next_hook"):
                prev_summaries.append(f"(직전 화 작가 메모: {ep['next_hook']})")

    client = _client(api_key)
    with client.messages.stream(
        model=MODEL,
        max_tokens=40000,
        thinking={"type": "adaptive"},
        output_config={
            "effort": "high",
            "format": {"type": "json_schema", "schema": EPISODE_SCHEMA},
        },
        system=_episode_system_prompt(bible),
        messages=[{
            "role": "user",
            "content": _episode_user_prompt(ep_num, prev_summaries, prev_tail, instructions),
        }],
    ) as stream:
        chars = 0
        for text in stream.text_stream:
            chars += len(text)
            if on_progress:
                on_progress(chars)
        message = stream.get_final_message()

    raw = next(b.text for b in message.content if b.type == "text")
    ep = json.loads(raw)
    ep["number"] = ep_num
    ep["chars"] = len(ep["content"])

    # 저장: json(이어쓰기용) + txt(문피아 붙여넣기용)
    ep_dir = os.path.join(PROJECTS_DIR, slug, "episodes")
    os.makedirs(ep_dir, exist_ok=True)
    with open(os.path.join(ep_dir, f"ep{ep_num:03d}.json"), "w", encoding="utf-8") as f:
        json.dump(ep, f, ensure_ascii=False, indent=2)
    with open(os.path.join(ep_dir, f"ep{ep_num:03d}.txt"), "w", encoding="utf-8") as f:
        f.write(f"{ep_num}화. {ep['title']}\n\n{ep['content']}\n")
    return ep


# ─────────────────────────── 터미널 실행 ───────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(description="문피아 현대판타지 웹소설 자동 집필기")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_new = sub.add_parser("new", help="새 작품 기획")
    p_new.add_argument("concept", help="소재 한 줄 (예: '회귀한 F급 헌터가 미래 지식으로 성장')")

    p_write = sub.add_parser("write", help="다음 화 집필")
    p_write.add_argument("slug", help="작품 폴더 이름 (novel_projects/ 아래)")
    p_write.add_argument("--note", default="", help="이번 화 지시사항 (선택)")

    sub.add_parser("list", help="작품 목록 보기")

    args = parser.parse_args()

    if args.cmd != "list" and not os.getenv("ANTHROPIC_API_KEY"):
        print("⚠️  환경변수 ANTHROPIC_API_KEY 가 없습니다.\n"
              "   터미널에서 먼저:  export ANTHROPIC_API_KEY='발급받은_키'", file=sys.stderr)
        sys.exit(1)

    if args.cmd == "list":
        for p in list_projects():
            print(f"  {p['slug']}  「{p['title']}」  {p['episodes']}화까지 집필됨")
        if not list_projects():
            print("  (아직 작품이 없습니다. new 명령으로 만들어 보세요)")

    elif args.cmd == "new":
        print(f"📝 '{args.concept}' 소재로 작품을 기획하는 중... (1~2분)")
        slug = create_project(args.concept)
        bible = load_bible(slug)
        print(f"\n✅ 작품 기획 완료!  「{bible['title']}」")
        print(f"   - 한 줄 소개: {bible['logline']}")
        print(f"   - 폴더: novel_projects/{slug}")
        print(f"\n다음 화 쓰기:  python novel_engine.py write {slug}")

    elif args.cmd == "write":
        n = episode_count(args.slug) + 1
        print(f"✍️  {n}화 집필 중... (2~5분, 5,000자 이상 원고)")
        ep = write_next_episode(args.slug, instructions=args.note,
                                on_progress=lambda c: print(f"\r   생성 중... {c:,}자", end=""))
        print(f"\n\n✅ {ep['number']}화 「{ep['title']}」 완성! (공백 포함 {ep['chars']:,}자)")
        print(f"   - 원고 파일: novel_projects/{args.slug}/episodes/ep{ep['number']:03d}.txt")
        print("   - 파일을 열어 전체 복사 → 문피아 회차 등록에 붙여넣으세요.")


if __name__ == "__main__":
    main()
