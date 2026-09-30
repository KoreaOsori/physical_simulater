"""탐구형 챗봇 모드 (docs/36). 기존 인간 거시 커넥톰 챗봇(docs/30-31)과
의도적으로 분리된 별도 엔드포인트다 -- 그 챗봇은 이 프로젝트 로컬 DB
밖으로 절대 안 나가는 게 핵심 규율인데, 이건 정반대로 OpenAI Responses
API의 실제 `web_search` 도구를 써서 자유롭게 외부 자료(논문, 리뷰,
뉴스 등)를 찾아 답한다. 개인 로컬 탐구용, 배포 대상 아님 -- 답변은
항상 실제 출처(URL)와 함께 나오고, "검증된 사실이 아니라 웹 검색 기반
참고 답변"이라는 고지가 고정으로 붙는다.

`web_search` 도구 사용은 이번 세션에 실제로 호출해서 확인한 실제 응답
구조를 그대로 따른다: `response.output`은
[reasoning, web_search_call, reasoning, message, ...] 형태의 아이템
목록이고, `message` 아이템의 `content[].annotations[]`에 실제
`url_citation`(url, title)이 들어있다."""

from __future__ import annotations

import logging

from openai import OpenAI

from app.core.config import get_settings
from app.lab.schemas import ExploreChatCitation, ExploreChatResponse

logger = logging.getLogger(__name__)

_HONESTY_NOTE = (
    "이 답변은 이 프로젝트의 검증된 로컬 데이터가 아니라 실시간 웹 검색 결과(또는 모델 자체 지식)를 "
    "바탕으로 생성됐습니다 — 이 프로젝트의 다른 챗봇(질환/영역 챗봇, docs/30)과 달리 사실 확인 없이 "
    "생성될 수 있습니다. 아래 출처를 직접 확인하세요."
)

_INSTRUCTIONS = (
    "당신은 신경과학을 탐구하는 개인 로컬 연구 도구의 보조 도우미입니다. 필요하면 실제 웹 검색 도구를 "
    "사용해 최신 문헌이나 실제 자료를 찾아 답하세요. 답변에 실제로 근거로 쓴 내용은 반드시 검색으로 찾은 "
    "실제 출처를 인용하세요 — 존재하지 않는 논문이나 출처를 지어내지 마세요. 확실하지 않은 내용은 "
    "확실하지 않다고 명시하세요. 신경과학·생물학과 무관한 질문은 정중히 범위 밖이라고 답하세요. "
    "한국어로, 4-6문장 이내로 답하세요."
)


def answer_explore_chat(message: str) -> ExploreChatResponse:
    settings = get_settings()
    if not settings.openai_api_key:
        return ExploreChatResponse(
            answer="챗봇이 아직 설정되지 않았습니다 (OPENAI_API_KEY 없음).",
            citations=[],
            used_web_search=False,
            honesty_note=_HONESTY_NOTE,
        )

    client = OpenAI(api_key=settings.openai_api_key)
    try:
        response = client.responses.create(
            model="gpt-5-mini",
            instructions=_INSTRUCTIONS,
            input=message,
            tools=[{"type": "web_search"}],
        )
    except Exception:
        logger.exception("Explore chat OpenAI call failed")
        return ExploreChatResponse(
            answer="지금은 답을 생성할 수 없습니다 (일시적인 오류) — 잠시 후 다시 시도해주세요.",
            citations=[],
            used_web_search=False,
            honesty_note=_HONESTY_NOTE,
        )

    used_web_search = False
    citations: list[ExploreChatCitation] = []
    seen_urls: set[str] = set()

    for item in response.output:
        item_type = getattr(item, "type", None)
        if item_type == "web_search_call":
            used_web_search = True
        elif item_type == "message":
            for content in getattr(item, "content", []) or []:
                for annotation in getattr(content, "annotations", []) or []:
                    if getattr(annotation, "type", None) != "url_citation":
                        continue
                    url = annotation.url
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)
                    citations.append(ExploreChatCitation(url=url, title=getattr(annotation, "title", None) or url))

    return ExploreChatResponse(
        answer=response.output_text,
        citations=citations,
        used_web_search=used_web_search,
        honesty_note=_HONESTY_NOTE,
    )
