"""연구소(Lab) 탐구형 챗봇 모드 테스트 (docs/36). OpenAI 호출은 fake
client로 모킹(docs/30의 human_chat 테스트와 같은 패턴) -- 실제 web_search
호출로 하는 라이브 확인은 문서의 "검증" 절에 남긴다(테스트마다 과금되는
걸 피하기 위함). fake 객체들의 속성 구조(item.type, content.annotations,
annotation.type/url/title)는 이번 세션에 실제로 호출해서 확인한 실제
OpenAI Responses API 응답 구조를 그대로 따른다."""

from fastapi.testclient import TestClient

from app.lab import explore_chat
from app.main import app

client = TestClient(app)


class _FakeAnnotation:
    def __init__(self, url: str, title: str | None = None, kind: str = "url_citation") -> None:
        self.type = kind
        self.url = url
        self.title = title


class _FakeContent:
    def __init__(self, annotations: list) -> None:
        self.annotations = annotations


class _FakeMessageItem:
    def __init__(self, content: list) -> None:
        self.type = "message"
        self.content = content


class _FakeWebSearchCallItem:
    def __init__(self) -> None:
        self.type = "web_search_call"


class _FakeResponse:
    def __init__(self, output_text: str, output: list) -> None:
        self.output_text = output_text
        self.output = output


class _FakeResponses:
    def __init__(self, response: _FakeResponse) -> None:
        self._response = response
        self.last_call_kwargs: dict | None = None

    def create(self, **kwargs):
        self.last_call_kwargs = kwargs
        return self._response


class _FakeOpenAI:
    def __init__(self, response: _FakeResponse, api_key: str | None = None) -> None:
        self.responses = _FakeResponses(response)


def test_answer_explore_chat_parses_web_search_and_citations(monkeypatch) -> None:
    fake_response = _FakeResponse(
        output_text="테스트 답변입니다.",
        output=[
            _FakeWebSearchCallItem(),
            _FakeMessageItem(
                [
                    _FakeContent(
                        [
                            _FakeAnnotation("https://example.com/a", "Source A"),
                            _FakeAnnotation("https://example.com/b", "Source B"),
                        ]
                    )
                ]
            ),
        ],
    )
    fake_client = _FakeOpenAI(fake_response)
    monkeypatch.setattr(explore_chat, "OpenAI", lambda api_key=None: fake_client)

    response = explore_chat.answer_explore_chat("아무 질문")

    assert response.answer == "테스트 답변입니다."
    assert response.used_web_search is True
    assert [c.url for c in response.citations] == ["https://example.com/a", "https://example.com/b"]
    assert response.citations[0].title == "Source A"
    assert response.honesty_note
    # web_search tool must actually be requested
    assert fake_client.responses.last_call_kwargs["tools"] == [{"type": "web_search"}]


def test_answer_explore_chat_dedupes_repeated_citation_urls(monkeypatch) -> None:
    fake_response = _FakeResponse(
        output_text="테스트.",
        output=[
            _FakeMessageItem(
                [
                    _FakeContent(
                        [
                            _FakeAnnotation("https://example.com/a", "First mention"),
                            _FakeAnnotation("https://example.com/a", "Second mention, same url"),
                        ]
                    )
                ]
            )
        ],
    )
    fake_client = _FakeOpenAI(fake_response)
    monkeypatch.setattr(explore_chat, "OpenAI", lambda api_key=None: fake_client)

    response = explore_chat.answer_explore_chat("아무 질문")

    assert len(response.citations) == 1


def test_answer_explore_chat_handles_no_search_performed(monkeypatch) -> None:
    # The model may answer from its own knowledge without calling the
    # search tool -- used_web_search must honestly reflect that.
    fake_response = _FakeResponse(output_text="검색 없이 답변.", output=[_FakeMessageItem([_FakeContent([])])])
    fake_client = _FakeOpenAI(fake_response)
    monkeypatch.setattr(explore_chat, "OpenAI", lambda api_key=None: fake_client)

    response = explore_chat.answer_explore_chat("아무 질문")

    assert response.used_web_search is False
    assert response.citations == []


def test_answer_explore_chat_fails_loudly_on_api_error(monkeypatch) -> None:
    class _BrokenOpenAI:
        def __init__(self, api_key=None):
            self.responses = self

        def create(self, **kwargs):
            raise RuntimeError("simulated API failure")

    monkeypatch.setattr(explore_chat, "OpenAI", lambda api_key=None: _BrokenOpenAI())

    response = explore_chat.answer_explore_chat("아무 질문")

    assert "오류" in response.answer or "지금은" in response.answer
    assert response.citations == []


def test_explore_chat_endpoint_returns_not_configured_when_key_missing(monkeypatch) -> None:
    from app.core import config as config_module

    monkeypatch.setattr(config_module.get_settings(), "openai_api_key", "")
    response = client.post("/api/lab/explore-chat", json={"message": "안녕"})
    assert response.status_code == 200
    assert "설정" in response.json()["answer"]
