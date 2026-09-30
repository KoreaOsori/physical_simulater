"use client";

import { useEffect, useRef, useState } from "react";

import { LOBE_LABEL_KO, type Lobe } from "@/features/connectome-viewer/lib/human-lobes";
import { postHumanChatMessage } from "@/shared/lib/api-client";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  sourcesSummary?: string;
}

interface ChatPanelProps {
  activeNetwork: string;
  visibleRegionIds: string[];
  selectedDisorderName: string | null;
  /** Bubbles up a disorder/region citation's region ids so the page can
   * merge them into HumanMacroCanvas's additive coloring (flat red, same
   * as the disorder panel) -- this component has no idea how highlighting
   * actually works in the 3D scene, it just reports it. */
  onHighlightRegions: (regionIds: string[]) => void;
  /** Bubbles up which lobes were requested ("전두엽 보여줘") -- kept
   * separate from onHighlightRegions because a lobe view gets its own
   * per-lobe color, not the disorder highlight's flat red (see docs/30's
   * "네트워크 vs 해부학" section). */
  onShowLobes: (lobes: Lobe[]) => void;
}

/** Compact, human-readable citation line instead of dumping every raw
 * source id ("region:42, region:43, ..." for a 60-region answer is not
 * useful to read -- the 3D highlight already shows WHICH regions, so this
 * just needs to say "region citation, N of them" for those, and show real
 * names for disorder/gene citations, which already read fine as-is minus
 * their kind prefix). Real user feedback: the previous version's raw id
 * dump was flagged as noisy/redundant with the on-screen highlight. */
function summarizeSources(sourceIds: string[]): string | undefined {
  if (sourceIds.length === 0) return undefined;
  const regionCount = sourceIds.filter((s) => s.startsWith("region:")).length;
  const disorderNames = sourceIds.filter((s) => s.startsWith("disorder:")).map((s) => s.slice("disorder:".length));
  const geneSymbols = sourceIds.filter((s) => s.startsWith("gene:")).map((s) => s.slice("gene:".length));

  const parts: string[] = [];
  if (regionCount > 0) parts.push(`영역 ${regionCount}개(3D 화면에 표시)`);
  if (disorderNames.length > 0) parts.push(disorderNames.join(", "));
  if (geneSymbols.length > 0) parts.push(geneSymbols.join(", "));
  return parts.length > 0 ? `출처: ${parts.join(" · ")}` : undefined;
}

/** DB-grounded chat panel (docs/30-human-macro-chat-panel.md) -- answers
 * only from this project's own already-cited data (region notes, disorder
 * descriptions, gene descriptions), never free LLM recall. Placed in the
 * empty space below the "해부 단계" dive-reveal slider (see .layer-panel in
 * globals.css). Same self-contained fetch/render composition as
 * AblationPanel.tsx/ResearchTrendsPanel.tsx, but request-per-message
 * instead of one static fetch. */
export function ChatPanel({ activeNetwork, visibleRegionIds, selectedDisorderName, onHighlightRegions, onShowLobes }: ChatPanelProps) {
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
    const userMessage: ChatMessage = { id: `u-${Date.now()}`, role: "user", text };
    setMessages((prev) => [...prev, userMessage]);
    setPending(true);
    try {
      const response = await postHumanChatMessage({
        message: text,
        active_network: activeNetwork,
        visible_region_ids: visibleRegionIds,
        selected_disorder_name: selectedDisorderName,
      });
      setMessages((prev) => [
        ...prev,
        { id: `a-${Date.now()}`, role: "assistant", text: response.answer, sourcesSummary: summarizeSources(response.used_source_ids) },
      ]);
      if (response.highlighted_region_ids.length > 0) {
        onHighlightRegions(response.highlighted_region_ids);
      }
      if (response.requested_lobes.length > 0) {
        onShowLobes(response.requested_lobes as Lobe[]);
      }
    } catch (error: unknown) {
      console.error("Failed to send human chat message", error);
      setMessages((prev) => [...prev, { id: `err-${Date.now()}`, role: "assistant", text: "답변을 가져오지 못했습니다 — 잠시 후 다시 시도해주세요." }]);
    } finally {
      setPending(false);
    }
  };

  return (
    <div className="human-chat-panel">
      <small>화면 데이터 기반 질문</small>
      {/* Always rendered (not just when messages exist) so this flex:1 area
       * always reserves the space between the heading and the input row --
       * otherwise the input sits right under the heading until the first
       * message arrives, then jumps to the bottom. The intro copy now lives
       * INSIDE the log as its empty-state content, not a separate
       * always-visible paragraph above a conditional log. */}
      <div className="human-chat-log" ref={listRef}>
        {messages.length === 0 ? (
          <p className="panel-copy">
            지금 보이는 영역·질환·유전자에 근거해서만 답합니다(논문 추측 없음). &ldquo;전두엽 보여줘&rdquo;처럼 물으면
            {" "}{Object.values(LOBE_LABEL_KO).join("·")} 4대엽이 각각 다른 색의 다면체(◆) 마커로, 질환/영역 질문은 3D
            씬에 빨간 구슬(●)로 표시됩니다. &ldquo;브로카 영역&rdquo;·&ldquo;베르니케 영역&rdquo;처럼 통칭으로 물어도
            실제 해부학적 위치를 찾아 답합니다.
          </p>
        ) : (
          <>
            {messages.map((m) => (
              <div key={m.id} className={m.role === "user" ? "human-chat-msg user" : "human-chat-msg assistant"}>
                <p>{m.text}</p>
                {m.sourcesSummary && <em>{m.sourcesSummary}</em>}
              </div>
            ))}
            {pending && <div className="human-chat-msg assistant human-chat-pending">답변 생성 중…</div>}
          </>
        )}
      </div>
      <form
        className="human-chat-input"
        onSubmit={(e) => {
          e.preventDefault();
          void send();
        }}
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="예: 이 영역은 뭐야? / 전두엽 보여줘"
          disabled={pending}
        />
        <button type="submit" disabled={pending || !input.trim()}>
          전송
        </button>
      </form>
    </div>
  );
}
