"""Human macro connectome chat panel (docs/30-human-macro-chat-panel.md,
docs/31-human-chat-semantic-search.md) -- DB-grounded only. Calls OpenAI's
gpt-5-mini (Responses API) but constrains it to answer from a context block
built entirely out of this project's own already-cited data
(app/data/human_chat_context.py's retrieval: on-screen context + keyword
matching + docs/31's embedding-based semantic search) -- never free recall
of outside papers, matching this project's honesty convention elsewhere
(see docs/00's principle, docs/21/26/28's citation discipline).

Region highlighting has two independent, visually distinct sources, both
computed from real data rather than asked of the model directly:
- A lobe request ("전두엽 보여줘") -> `requested_lobes` (just the lobe
  keys, e.g. ["frontal"]) is returned; the FRONTEND resolves this into
  actual region ids and a distinct color per lobe (it already has every
  region's real anatomical_label loaded) -- see app/data/human_lobes.py for
  the backend's mirror of that same real AAL mapping (used here only to
  detect which lobes were mentioned, not to compute colors -- colors are a
  presentation concern, kept out of the API response). This is "distinct
  anatomical areas, each its own color" -- a genuinely different semantic
  from a disorder highlight ("these regions are collectively implicated",
  one color), which is why it's a separate response field instead of being
  merged into highlighted_region_ids.
- Any answer that actually cites a region or disorder source (via the
  required `used_source_ids` in its structured output) -> that region's id,
  or a disorder's whole real affected-region set
  (DisorderAssociation.region_ids, the exact data the disorder side panel
  already highlights from -- see docs/21) -- app/data/human_chat_context.py's
  `region_ids_for_used_sources`, returned in `highlighted_region_ids`.
"""

from __future__ import annotations

import json
import logging

from openai import OpenAI

from app.core.config import get_settings
from app.data.human_chat_context import (
    MAX_CORPUS_DOCS_PER_REQUEST,
    detect_named_area_synonyms,
    detect_requested_lobes,
    region_ids_for_used_sources,
    search_corpus,
    semantic_search_corpus,
)
from app.data.human_lobes import LOBE_LABEL_KO
from app.domain.schemas import HumanChatRequest, HumanChatResponse

logger = logging.getLogger(__name__)

# Reused verbatim from the disorder-panel's own hedge text (see
# backend/scripts/human_anatomical_labels.py's _COMPLEX_CAVEAT) -- the
# model is told to use text like this rather than invent its own hedging
# phrasing when a topic is genuinely multi-causal/uncertain.
_HEDGE_EXAMPLE = (
    '"아래 부위들은 문헌에서 반복적으로 이상 소견이 보고된 곳일 뿐, '
    '\'이 부위가 원인이다\'라는 뜻이 아니다"'
)

_ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string", "description": "한국어 답변, 3-4문장 이내."},
        "used_source_ids": {
            "type": "array",
            "items": {"type": "string"},
            "description": "답변에 실제로 근거로 쓴 컨텍스트 항목의 id들.",
        },
    },
    "required": ["answer", "used_source_ids"],
    "additionalProperties": False,
}

_NO_CONTEXT_NOTE = "이 데이터셋에서 관련 항목을 찾지 못했습니다 — 화면에 있는 영역/질환/유전자에 대해서만 답할 수 있습니다."

# A live user hit this exact contradiction: asking about a named area
# ("브로카 영역") got the no-context refusal even though search_corpus had
# already retrieved real matching region docs into the prompt -- confirmed
# via repeated live calls that this is genuine gpt-5-mini non-determinism,
# not a retrieval bug (same instructions/context, sometimes right, sometimes
# refuses). A single retry with a more forceful nudge, only in this specific
# contradictory case, is cheap and bounded (never loops).
_RETRY_NUDGE = (
    "\n\n다시 한 번: 위 '컨텍스트' 목록에 이미 관련 항목이 있습니다 — 방금 "
    f'"{_NO_CONTEXT_NOTE}"라고 답한 건 틀렸습니다. 이번에는 반드시 위 컨텍스트 항목들을 '
    "실제로 사용해서 답하세요."
)


def _build_instructions(context_docs, requested_lobes: list[str], named_areas=()) -> str:
    if context_docs:
        context_block = "\n".join(f"- [{doc.id}] {doc.text}" for doc in context_docs)
    else:
        context_block = "(관련 항목 없음)"

    named_area_note = ""
    if named_areas:
        # Mirrors lobe_note's phrasing/urgency below -- a softer "참고"-only
        # version of this note was found live to be inconsistently
        # overridden by rule 1's "no relevant context" framing (gpt-5-mini
        # sometimes fell back to the no-context reply even with 14 matching
        # Temporal_Sup docs in context) -- an explicit "don't use that exact
        # phrase for this case" instruction, same as the lobe carve-out,
        # reads more reliably.
        canonical_names = ", ".join(synonym.canonical_ko for synonym in named_areas)
        named_area_note = (
            f"\n\n중요: 사용자가 쓴 표현 중 일부({canonical_names})는 이 데이터셋의 AAL 명칭이 아닌 "
            "통칭(널리 알려진 별명)입니다 — 위 '컨텍스트' 목록에 이미 그 통칭에 해당하는 실제 해부학적 "
            "영역 설명이 포함되어 있으니, 이 경우는 '관련 항목이 없음'이 아닙니다. 규칙 1의 "
            f'"{_NO_CONTEXT_NOTE}" 문구를 이 질문에는 쓰지 말고, 위 컨텍스트를 사용해 통칭과 실제 '
            "해부학적 명칭을 연결해서 답하세요."
        )

    lobe_note = ""
    if requested_lobes:
        names = ", ".join(LOBE_LABEL_KO[lobe] for lobe in requested_lobes)
        lobe_note = (
            f"\n\n중요: 사용자가 {names} 표시를 요청했고, 시스템이 이미 3D 화면에서 해당 "
            "영역들을 강조했습니다(당신이 직접 하는 게 아니라 이미 처리 완료됨) — 이 요청은 "
            "'컨텍스트에 없는 질문'이 아니라 이미 성공적으로 수행된 액션이니 규칙 1의 "
            f'"{_NO_CONTEXT_NOTE}" 문구를 쓰지 말고, 대신 "{names} 영역을 화면에 표시했습니다" '
            "같은 확인 문장으로 답하세요."
        )

    return (
        "당신은 이 프로젝트(인간 뇌 커넥톰 3D 시각화 도구)의 화면에 이미 표시된 "
        "실제 데이터에만 근거해 답하는 도우미입니다.\n\n"
        "규칙:\n"
        "1. 아래 '컨텍스트' 목록에 없는 내용은 절대 답하지 말고(단, 엽 보기 요청은 예외 — "
        "아래 '중요' 참고), "
        f'관련 항목이 없으면 정확히 이렇게 답하세요: "{_NO_CONTEXT_NOTE}"\n'
        "2. 논문을 새로 인용하거나 컨텍스트에 없는 사실을 추측하지 마세요 — "
        "이 프로젝트는 검증되지 않은 내용을 절대 지어내지 않습니다.\n"
        "3. 질환/병변-증상 관련 컨텍스트 항목을 답할 때만, 그 항목 설명에 이미 있는 "
        "인과관계 헤지 문구를 그대로 반영하세요(예: 컨텍스트에 이미 있다면 "
        f"{_HEDGE_EXAMPLE}) — 단순 해부학적 위치·기능 설명(질환이 아닌 region 항목)에는 "
        "이 헤지를 억지로 붙이지 마세요.\n"
        "4. 답변에 실제로 쓴 컨텍스트 항목의 대괄호 태그를 used_source_ids에 "
        "'대괄호 안 문자열 그대로'(예: 'region:42', 'disorder:대뇌색맹') 나열하세요 — "
        "본문 설명 중에 따로 언급된 다른 숫자(예: '영역 id 42')와 혼동하지 말고, "
        "반드시 줄 맨 앞 [ ] 안의 문자열만 쓰세요. 안 쓴 항목은 넣지 마세요.\n"
        "5. 한국어로, 3-4문장 이내로 간결하게 답하세요.\n\n"
        f"컨텍스트:\n{context_block}"
        f"{named_area_note}"
        f"{lobe_note}"
    )


def answer_human_chat(request: HumanChatRequest) -> HumanChatResponse:
    settings = get_settings()
    if not settings.openai_api_key:
        return HumanChatResponse(
            answer="챗봇이 아직 설정되지 않았습니다 (OPENAI_API_KEY 없음).",
            used_source_ids=[],
            highlighted_region_ids=[],
            requested_lobes=[],
        )

    requested_lobes = detect_requested_lobes(request.message)
    named_areas = detect_named_area_synonyms(request.message)
    client = OpenAI(api_key=settings.openai_api_key)

    context_docs = search_corpus(
        request.message,
        request.active_network,
        request.visible_region_ids,
        request.selected_disorder_name,
    )
    # docs/31: a second, additive retrieval channel over the same real
    # corpus -- catches paraphrased questions that share no literal keyword
    # with any region/disorder/gene name (channel 2 above already handles
    # exact/near-exact names). Never replaces channel 1/2; only fills gaps
    # they leave, and silently contributes nothing if it fails (see its own
    # docstring).
    semantic_docs = semantic_search_corpus(request.message, client, exclude_ids={doc.id for doc in context_docs})
    context_docs = (context_docs + semantic_docs)[:MAX_CORPUS_DOCS_PER_REQUEST]

    instructions = _build_instructions(context_docs, requested_lobes, named_areas)

    def _call(instr: str) -> tuple[str, list[str]]:
        response = client.responses.create(
            model="gpt-5-mini",
            instructions=instr,
            input=request.message,
            text={"format": {"type": "json_schema", "name": "human_chat_answer", "schema": _ANSWER_SCHEMA, "strict": True}},
        )
        parsed = json.loads(response.output_text)
        return parsed["answer"], [sid for sid in parsed.get("used_source_ids", []) if isinstance(sid, str)]

    try:
        answer, used_source_ids = _call(instructions)
        # See _RETRY_NUDGE's comment -- a refusal despite real retrieved
        # context is almost always the model, not a real "no data" case.
        if answer.strip() == _NO_CONTEXT_NOTE and context_docs:
            logger.warning("Human chat refused despite non-empty context (%d docs); retrying once", len(context_docs))
            answer, used_source_ids = _call(instructions + _RETRY_NUDGE)
    except Exception:
        logger.exception("Human chat OpenAI call failed")
        # Even on API failure, still report requested_lobes -- the lobe
        # view itself is a deterministic Python action independent of the
        # LLM call, so a transient API error shouldn't undo it.
        return HumanChatResponse(
            answer="지금은 답을 생성할 수 없습니다 (일시적인 오류) — 잠시 후 다시 시도해주세요.",
            used_source_ids=[],
            highlighted_region_ids=[],
            requested_lobes=requested_lobes,
        )

    # The visual counterpart to the answer: whatever real region(s) the
    # model actually cited (a specific region, or a disorder's whole
    # affected-region set, see DisorderAssociation.region_ids / docs/21).
    highlighted_region_ids = region_ids_for_used_sources(used_source_ids)

    return HumanChatResponse(
        answer=answer,
        used_source_ids=used_source_ids,
        highlighted_region_ids=highlighted_region_ids,
        requested_lobes=requested_lobes,
    )
