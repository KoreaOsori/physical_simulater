"""Tests the retrieval/lobe logic and request/response wiring without
hitting the real OpenAI API (mocked client) -- see docs/30-human-macro-
chat-panel.md's "검증" section for the one real, manually-run live check."""

import json

import pytest
from fastapi.testclient import TestClient

from app.data.human_chat_context import (
    MAX_CORPUS_DOCS_PER_REQUEST,
    ChatCorpusDoc,
    _cosine_similarity,
    detect_named_area_synonyms,
    detect_requested_lobes,
    region_ids_for_lobes,
    search_corpus,
    semantic_search_corpus,
)
from app.data.human_data import get_macro_connectome
from app.data.human_lobes import lobe_for_anatomical_label
from app.domain.schemas import HumanChatRequest
from app.main import app
from app.simulation import human_chat_engine

client = TestClient(app)


def test_lobe_mapping_covers_every_real_aal_label_in_the_dataset() -> None:
    macro = get_macro_connectome()
    labeled = [r for r in macro.regions if r.anatomical_label]
    assert labeled  # sanity: the dataset actually has AAL labels (docs/19)
    unmapped = [r.anatomical_label for r in labeled if lobe_for_anatomical_label(r.anatomical_label) is None]
    assert unmapped == []


def test_detect_requested_lobes_only_matches_real_keywords() -> None:
    assert detect_requested_lobes("전두엽 보여줘") == ["frontal"]
    assert detect_requested_lobes("측두엽이랑 후두엽 보여줘") == ["temporal", "occipital"]
    assert detect_requested_lobes("이 영역은 뭐야?") == []


def test_region_ids_for_lobes_matches_real_region_count() -> None:
    ids = region_ids_for_lobes(["frontal"])
    assert len(ids) == 133  # cross-checked directly against the dataset this session


def test_detect_named_area_synonyms_matches_real_eponyms_including_a_typo() -> None:
    # "베로니카" is a real mishearing/typo of 베르니케 (Wernicke) a live user
    # query actually used -- both must resolve to the same canonical entry.
    assert [s.canonical_ko for s in detect_named_area_synonyms("베로니카 영역이 뭐야?")] == ["베르니케 영역"]
    assert [s.canonical_ko for s in detect_named_area_synonyms("베르니케 영역이 뭐야?")] == ["베르니케 영역"]
    assert [s.canonical_ko for s in detect_named_area_synonyms("브로카 영역은 어디야?")] == ["브로카 영역"]
    assert detect_named_area_synonyms("이 영역은 뭐야?") == []


def test_search_corpus_surfaces_real_regions_for_a_named_area_synonym() -> None:
    # 베로니카(Wernicke) has no AAL label of its own -- this must still
    # surface the real posterior-STG parcel (Temporal_Sup) instead of
    # dead-ending with "no context found" (a live user query hit exactly
    # this dead end before the synonym mapping was added).
    docs = search_corpus("전두엽 베로니카 영역이 궁금해", None, [], None)
    assert any(d.region_id and "Temporal_Sup" in (d.text.split(" (", 1)[0]) for d in docs)


def test_search_corpus_includes_visible_context_and_keyword_matches() -> None:
    macro = get_macro_connectome()
    some_region = next(r for r in macro.regions if r.anatomical_note)
    docs = search_corpus("아무 질문", None, [some_region.id], None)
    assert any(d.region_id == some_region.id for d in docs)

    some_disorder = macro.known_disorders[0]
    docs2 = search_corpus(f"{some_disorder.name}에 대해 알려줘", None, [], None)
    assert any(d.id == f"disorder:{some_disorder.name}" for d in docs2)


def test_cosine_similarity_basic_cases() -> None:
    assert _cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert _cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
    assert _cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)
    assert _cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0  # zero vector -- no divide-by-zero crash


class _FakeEmbeddingResponse:
    def __init__(self, vector: list[float]) -> None:
        self.data = [type("_Item", (), {"embedding": vector})()]


class _FakeEmbeddings:
    def __init__(self, vector: list[float] | None = None, raise_error: bool = False) -> None:
        self._vector = vector
        self._raise_error = raise_error
        self.last_call_kwargs: dict | None = None

    def create(self, **kwargs):
        self.last_call_kwargs = kwargs
        if self._raise_error:
            raise RuntimeError("simulated embedding API failure")
        return _FakeEmbeddingResponse(self._vector)


class _FakeEmbeddingClient:
    def __init__(self, vector: list[float] | None = None, raise_error: bool = False) -> None:
        self.embeddings = _FakeEmbeddings(vector, raise_error)


def test_semantic_search_corpus_ranks_by_similarity_and_respects_threshold(monkeypatch) -> None:
    macro = get_macro_connectome()
    disorder_a, disorder_b = macro.known_disorders[0], macro.known_disorders[1]
    fake_embeddings = {
        f"disorder:{disorder_a.name}": [1.0, 0.0],  # identical to query -> similarity 1.0
        f"disorder:{disorder_b.name}": [0.0, 1.0],  # orthogonal -> similarity 0.0, below threshold
    }
    monkeypatch.setattr("app.data.human_chat_context._load_doc_embeddings", lambda: fake_embeddings)
    client = _FakeEmbeddingClient(vector=[1.0, 0.0])

    docs = semantic_search_corpus("아무 질문", client, exclude_ids=set())

    assert [d.id for d in docs] == [f"disorder:{disorder_a.name}"]


def test_semantic_search_corpus_excludes_already_selected_doc_ids(monkeypatch) -> None:
    macro = get_macro_connectome()
    disorder_a = macro.known_disorders[0]
    fake_embeddings = {f"disorder:{disorder_a.name}": [1.0, 0.0]}
    monkeypatch.setattr("app.data.human_chat_context._load_doc_embeddings", lambda: fake_embeddings)
    client = _FakeEmbeddingClient(vector=[1.0, 0.0])

    docs = semantic_search_corpus("아무 질문", client, exclude_ids={f"disorder:{disorder_a.name}"})

    assert docs == []


def test_semantic_search_corpus_returns_empty_without_calling_api_when_no_embeddings_file(monkeypatch) -> None:
    monkeypatch.setattr("app.data.human_chat_context._load_doc_embeddings", lambda: {})
    client = _FakeEmbeddingClient(vector=[1.0, 0.0])

    docs = semantic_search_corpus("아무 질문", client, exclude_ids=set())

    assert docs == []
    assert client.embeddings.last_call_kwargs is None  # never even tried to embed the query


def test_semantic_search_corpus_degrades_gracefully_on_api_failure(monkeypatch) -> None:
    macro = get_macro_connectome()
    disorder_a = macro.known_disorders[0]
    monkeypatch.setattr("app.data.human_chat_context._load_doc_embeddings", lambda: {f"disorder:{disorder_a.name}": [1.0, 0.0]})
    client = _FakeEmbeddingClient(raise_error=True)

    docs = semantic_search_corpus("아무 질문", client, exclude_ids=set())

    assert docs == []


class _FakeResponse:
    def __init__(self, output_text: str) -> None:
        self.output_text = output_text


class _FakeResponses:
    def __init__(self, output_text: str) -> None:
        self._output_text = output_text
        self.last_call_kwargs: dict | None = None

    def create(self, **kwargs):
        self.last_call_kwargs = kwargs
        return _FakeResponse(self._output_text)


class _FakeOpenAI:
    def __init__(self, output_text: str, api_key: str | None = None) -> None:
        self.responses = _FakeResponses(output_text)
        # Zero vector -> _cosine_similarity's zero-norm guard makes every
        # real corpus doc score exactly 0.0, always below the semantic
        # threshold -- keeps these chat-completion-focused tests decoupled
        # from the content of the real committed embeddings file (semantic
        # search's own behavior is tested separately, against fake
        # embeddings, above).
        self.embeddings = _FakeEmbeddings(vector=[0.0] * 256)


class _FakeResponsesSequence:
    """Returns a different output_text on each successive call -- used to
    test the retry-on-contradictory-refusal path (see human_chat_engine's
    _RETRY_NUDGE)."""

    def __init__(self, output_texts: list[str]) -> None:
        self._output_texts = output_texts
        self.call_count = 0

    def create(self, **kwargs):
        text = self._output_texts[min(self.call_count, len(self._output_texts) - 1)]
        self.call_count += 1
        return _FakeResponse(text)


class _FakeOpenAISequence:
    def __init__(self, output_texts: list[str], api_key: str | None = None) -> None:
        self.responses = _FakeResponsesSequence(output_texts)
        self.embeddings = _FakeEmbeddings(vector=[0.0] * 256)  # see _FakeOpenAI's comment


def test_answer_human_chat_parses_model_output_and_reports_sources(monkeypatch) -> None:
    fake_json = json.dumps({"answer": "테스트 답변입니다.", "used_source_ids": ["region:foo"]})
    fake_client = _FakeOpenAI(fake_json)
    monkeypatch.setattr(human_chat_engine, "OpenAI", lambda api_key=None: fake_client)

    request = HumanChatRequest(message="아무 질문", active_network=None, visible_region_ids=[], selected_disorder_name=None)
    response = human_chat_engine.answer_human_chat(request)

    assert response.answer == "테스트 답변입니다."
    assert response.used_source_ids == ["region:foo"]
    assert response.highlighted_region_ids == []
    # instructions must have been given a strict json_schema format, not
    # left to plain free text.
    assert fake_client.responses.last_call_kwargs["text"]["format"]["type"] == "json_schema"


def test_answer_human_chat_reports_requested_lobes_not_highlighted_region_ids(monkeypatch) -> None:
    """Lobe regions are resolved client-side (frontend already has every
    region's real anatomical_label loaded, see docs/30) so it can assign
    each lobe its own color -- the backend only reports WHICH lobes, not a
    flat single-color region id list (that's reserved for disorder/region
    citations, see the next test)."""
    fake_json = json.dumps({"answer": "전두엽을 표시했습니다.", "used_source_ids": []})
    fake_client = _FakeOpenAI(fake_json)
    monkeypatch.setattr(human_chat_engine, "OpenAI", lambda api_key=None: fake_client)

    request = HumanChatRequest(message="전두엽 보여줘", active_network=None, visible_region_ids=[], selected_disorder_name=None)
    response = human_chat_engine.answer_human_chat(request)

    assert response.requested_lobes == ["frontal"]
    assert response.highlighted_region_ids == []


def test_answer_human_chat_reports_multiple_requested_lobes(monkeypatch) -> None:
    fake_json = json.dumps({"answer": "측두엽과 후두엽을 표시했습니다.", "used_source_ids": []})
    fake_client = _FakeOpenAI(fake_json)
    monkeypatch.setattr(human_chat_engine, "OpenAI", lambda api_key=None: fake_client)

    request = HumanChatRequest(message="측두엽이랑 후두엽 보여줘", active_network=None, visible_region_ids=[], selected_disorder_name=None)
    response = human_chat_engine.answer_human_chat(request)

    assert response.requested_lobes == ["temporal", "occipital"]


def test_answer_human_chat_highlights_regions_for_a_cited_disorder(monkeypatch) -> None:
    macro = get_macro_connectome()
    disorder = macro.known_disorders[0]
    fake_json = json.dumps({"answer": "테스트.", "used_source_ids": [f"disorder:{disorder.name}"]})
    fake_client = _FakeOpenAI(fake_json)
    monkeypatch.setattr(human_chat_engine, "OpenAI", lambda api_key=None: fake_client)

    request = HumanChatRequest(message=disorder.name, active_network=None, visible_region_ids=[], selected_disorder_name=None)
    response = human_chat_engine.answer_human_chat(request)

    assert set(response.highlighted_region_ids) == set(disorder.region_ids)


def test_answer_human_chat_highlights_a_cited_region() -> None:
    from app.data.human_chat_context import region_ids_for_used_sources

    macro = get_macro_connectome()
    some_region = next(r for r in macro.regions if r.anatomical_note)
    assert region_ids_for_used_sources([f"region:{some_region.id}"]) == [some_region.id]


def test_region_ids_for_used_sources_ignores_unknown_ids() -> None:
    from app.data.human_chat_context import region_ids_for_used_sources

    assert region_ids_for_used_sources(["region:not-a-real-id", "disorder:존재하지않음", "gene:BDNF"]) == []


def test_answer_human_chat_retries_once_when_model_refuses_despite_real_context(monkeypatch) -> None:
    # Live bug: gpt-5-mini sometimes returned the "no relevant context"
    # refusal even though search_corpus had already retrieved real matching
    # docs (non-deterministic, confirmed via repeated live calls). A single
    # retry should recover the correct answer.
    from app.simulation.human_chat_engine import _NO_CONTEXT_NOTE

    macro = get_macro_connectome()
    some_disorder = macro.known_disorders[0]
    refusal_json = json.dumps({"answer": _NO_CONTEXT_NOTE, "used_source_ids": []})
    good_json = json.dumps({"answer": "재시도 후 정답입니다.", "used_source_ids": [f"disorder:{some_disorder.name}"]})
    fake_client = _FakeOpenAISequence([refusal_json, good_json])
    monkeypatch.setattr(human_chat_engine, "OpenAI", lambda api_key=None: fake_client)

    request = HumanChatRequest(message=f"{some_disorder.name}에 대해 알려줘", active_network=None, visible_region_ids=[], selected_disorder_name=None)
    response = human_chat_engine.answer_human_chat(request)

    assert fake_client.responses.call_count == 2
    assert response.answer == "재시도 후 정답입니다."
    assert set(response.highlighted_region_ids) == set(some_disorder.region_ids)


def test_answer_human_chat_does_not_retry_when_context_is_genuinely_empty(monkeypatch) -> None:
    # The refusal string is the CORRECT answer when context_docs really is
    # empty -- retrying would just waste a call and risk the model
    # hallucinating something to avoid repeating itself.
    from app.simulation.human_chat_engine import _NO_CONTEXT_NOTE

    refusal_json = json.dumps({"answer": _NO_CONTEXT_NOTE, "used_source_ids": []})
    fake_client = _FakeOpenAISequence([refusal_json, json.dumps({"answer": "이건 나오면 안 됨", "used_source_ids": []})])
    monkeypatch.setattr(human_chat_engine, "OpenAI", lambda api_key=None: fake_client)

    request = HumanChatRequest(message="전혀 관련 없는 아무말 대잔치", active_network=None, visible_region_ids=[], selected_disorder_name=None)
    response = human_chat_engine.answer_human_chat(request)

    assert fake_client.responses.call_count == 1
    assert response.answer == _NO_CONTEXT_NOTE


def test_answer_human_chat_merges_semantic_search_results_into_instructions(monkeypatch) -> None:
    """docs/31: a doc that ONLY the semantic channel found (not on-screen,
    no literal keyword match) must still reach the model's instructions."""
    fake_json = json.dumps({"answer": "테스트.", "used_source_ids": []})
    fake_client = _FakeOpenAI(fake_json)
    monkeypatch.setattr(human_chat_engine, "OpenAI", lambda api_key=None: fake_client)

    macro = get_macro_connectome()
    some_region = next(r for r in macro.regions if r.anatomical_note)
    semantic_doc = ChatCorpusDoc(
        id=f"region:{some_region.id}",
        text="이 텍스트는 키워드 매칭으로는 절대 안 걸리는 semantic-only 고유 문자열입니다",
        kind="region",
        region_id=some_region.id,
    )
    monkeypatch.setattr(human_chat_engine, "semantic_search_corpus", lambda message, client, exclude_ids: [semantic_doc])

    request = HumanChatRequest(message="전혀 다른 말투의 질문이야", active_network=None, visible_region_ids=[], selected_disorder_name=None)
    human_chat_engine.answer_human_chat(request)

    instructions = fake_client.responses.last_call_kwargs["instructions"]
    assert "semantic-only 고유 문자열" in instructions


def test_answer_human_chat_caps_merged_context_at_max_docs(monkeypatch) -> None:
    fake_json = json.dumps({"answer": "테스트.", "used_source_ids": []})
    fake_client = _FakeOpenAI(fake_json)
    monkeypatch.setattr(human_chat_engine, "OpenAI", lambda api_key=None: fake_client)

    keyword_docs = [ChatCorpusDoc(id=f"gene:K{i}", text=f"keyword doc {i}", kind="gene", region_id=None) for i in range(MAX_CORPUS_DOCS_PER_REQUEST)]
    semantic_docs = [ChatCorpusDoc(id=f"gene:S{i}", text=f"semantic doc {i}", kind="gene", region_id=None) for i in range(10)]
    monkeypatch.setattr(human_chat_engine, "search_corpus", lambda *args, **kwargs: keyword_docs)
    monkeypatch.setattr(human_chat_engine, "semantic_search_corpus", lambda *args, **kwargs: semantic_docs)

    request = HumanChatRequest(message="아무 질문", active_network=None, visible_region_ids=[], selected_disorder_name=None)
    human_chat_engine.answer_human_chat(request)

    instructions = fake_client.responses.last_call_kwargs["instructions"]
    assert "semantic doc" not in instructions  # keyword_docs alone already fill MAX_CORPUS_DOCS_PER_REQUEST
    assert instructions.count("keyword doc") == MAX_CORPUS_DOCS_PER_REQUEST


def test_answer_human_chat_fails_loudly_on_api_error(monkeypatch) -> None:
    class _BrokenOpenAI:
        def __init__(self, api_key=None):
            self.responses = self

        def create(self, **kwargs):
            raise RuntimeError("simulated API failure")

    monkeypatch.setattr(human_chat_engine, "OpenAI", lambda api_key=None: _BrokenOpenAI())

    request = HumanChatRequest(message="아무 질문", active_network=None, visible_region_ids=[], selected_disorder_name=None)
    response = human_chat_engine.answer_human_chat(request)

    assert "오류" in response.answer or "지금은" in response.answer
    assert response.used_source_ids == []


def test_chat_endpoint_returns_not_configured_when_key_missing(monkeypatch) -> None:
    from app.core import config as config_module

    monkeypatch.setattr(config_module.get_settings(), "openai_api_key", "")
    response = client.post("/api/human/chat", json={"message": "안녕"})
    assert response.status_code == 200
    assert "설정" in response.json()["answer"]
