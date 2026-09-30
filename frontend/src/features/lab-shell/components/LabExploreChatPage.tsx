"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";

import { postLabExploreChat } from "@/shared/lib/api-client";
import type { ExploreChatCitation } from "@/types/lab";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  citations?: ExploreChatCitation[];
  usedWebSearch?: boolean;
}

/** 연구소(Lab) — 탐구형 챗봇 모드 (docs/36). 인간 거시 커넥톰 페이지의
 * DB 근거 한정 챗봇(docs/30-31)과 정반대 성격 — 이 모드는 OpenAI의 실제
 * web_search 도구로 외부 자료를 자유롭게 찾아 답한다. 답변마다 실제 출처를
 * 클릭 가능한 링크로 항상 표시한다(OpenAI 이용약관 요구사항이자, 이
 * 프로젝트의 "근거를 항상 보여준다" 관행과도 맞음). */
export function LabExploreChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [pending, setPending] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight });
  }, [messages]);

  const send = async () => {
    const text = input.trim();
    if (!text || pending) return;
    setInput("");
    setMessages((prev) => [...prev, { id: `u-${Date.now()}`, role: "user", text }]);
    setPending(true);
    try {
      const response = await postLabExploreChat(text);
      setMessages((prev) => [
        ...prev,
        { id: `a-${Date.now()}`, role: "assistant", text: response.answer, citations: response.citations, usedWebSearch: response.used_web_search },
      ]);
    } catch (error: unknown) {
      console.error("Failed to send lab explore chat message", error);
      setMessages((prev) => [...prev, { id: `err-${Date.now()}`, role: "assistant", text: "답변을 가져오지 못했습니다 — 잠시 후 다시 시도해주세요." }]);
    } finally {
      setPending(false);
    }
  };

  return (
    <main className="lab-shell">
      <header className="topbar">
        <div className="brand">
          <b>∿</b> 신경 / <strong>연구소</strong>
          <i>β</i>
        </div>
        <div className="specimen-title">
          <span>탐구</span>
          <strong>탐구형 챗봇 모드</strong>
          <em>실시간 웹 검색 · 외부 자료</em>
        </div>
        <div className="top-status">
          <Link href="/lab" className="species-switch">
            ← 연구소
          </Link>
        </div>
      </header>
      <section className="lab-content lab-explore-chat-content">
        <div className="lab-honesty-banner">
          이 답변은 이 프로젝트의 검증된 로컬 데이터가 아니라 실시간 웹 검색 결과(또는 모델 자체 지식)를 바탕으로
          생성됩니다 — 인간 커넥톰 페이지의 DB 근거 한정 챗봇과 달리 사실 확인 없이 생성될 수 있습니다. 출처
          링크를 직접 확인하세요.
        </div>

        <div className="lab-explore-chat-log" ref={listRef}>
          {messages.length === 0 ? (
            <p className="panel-copy">신경과학 관련 질문을 자유롭게 물어보세요. 필요하면 실제 웹을 검색해 출처와 함께 답합니다.</p>
          ) : (
            <>
              {messages.map((m) => (
                <div key={m.id} className={m.role === "user" ? "human-chat-msg user" : "human-chat-msg assistant"}>
                  <p>{m.text}</p>
                  {m.role === "assistant" && m.usedWebSearch !== undefined && (
                    <em>{m.usedWebSearch ? "실제 웹 검색 사용됨" : "웹 검색 없이 모델 자체 지식으로 답변"}</em>
                  )}
                  {m.citations && m.citations.length > 0 && (
                    <div className="lab-citation-list">
                      {m.citations.map((c) => (
                        <a key={c.url} href={c.url} target="_blank" rel="noopener noreferrer" className="lab-citation-link">
                          {c.title}
                        </a>
                      ))}
                    </div>
                  )}
                </div>
              ))}
              {pending && <div className="human-chat-msg assistant human-chat-pending">답변 생성 중…</div>}
            </>
          )}
        </div>

        <form
          className="human-chat-input lab-explore-chat-input"
          onSubmit={(e) => {
            e.preventDefault();
            void send();
          }}
        >
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="예: 최근 발표된 커넥톰 관련 연구는?"
            disabled={pending}
          />
          <button type="submit" disabled={pending || !input.trim()}>
            전송
          </button>
        </form>
      </section>
    </main>
  );
}
