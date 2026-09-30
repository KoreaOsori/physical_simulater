"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { fetchLabHypotheses } from "@/shared/lib/api-client";
import type { HypothesisRecord, HypothesisVerdict } from "@/types/lab";

const VERDICT_LABEL: Record<HypothesisVerdict, string> = {
  supported: "지지됨",
  not_supported: "기각됨",
  inconclusive: "불확실",
};

/** 연구소(Lab) — 가설 노트 (docs/39). 다른 3개 연구소 도구(위상 분석/
 * 가상 실험실/탐구형 챗봇)와 유전자 후보 탐색기를 실제로 조합해 세운 가설
 * 6개(docs/39-40) + 가상 개체 폐루프로 세운 H7-H12(docs/46)와 그 실제 검증 기록 — "만약 X라면 Y일 것이다" 구조로 가설을 세우고,
 * 실제 도구를 돌려 나온 진짜 결과를 지지든 기각이든 정직하게 보여준다. */
export function LabHypothesisNotebookPage() {
  const [records, setRecords] = useState<HypothesisRecord[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchLabHypotheses()
      .then(setRecords)
      .catch((err: unknown) => {
        console.error("Failed to load hypothesis notebook", err);
        setError("불러오지 못했습니다 — 잠시 후 다시 시도해주세요.");
      });
  }, []);

  return (
    <main className="lab-shell">
      <header className="topbar">
        <div className="brand">
          <b>∿</b> 신경 / <strong>연구소</strong>
          <i>β</i>
        </div>
        <div className="specimen-title">
          <span>탐구</span>
          <strong>가설 노트</strong>
          <em>4개 도구를 조합한 실제 검증 기록</em>
        </div>
        <div className="top-status">
          <Link href="/lab" className="species-switch">
            ← 연구소
          </Link>
        </div>
      </header>
      <section className="lab-content">
        <div className="lab-honesty-banner">
          아래 30개는 이 연구소의 도구들을 실제로 조합해 세우고 검증한 가설입니다. 가설이 지지됐든
          기각됐든/혼재하든(예: H1, H6, H8, H12) 있는 그대로 기록했습니다 — H2-H6은 실제 Brian2 시뮬레이션·실제
          OpenAI 웹 검색·실제 대형 그래프 계산을 1회 수행한 결과, H7-H12는 가상 웜/초파리 폐루프의 실제 네트워크를
          그대로 돌려 예측을 먼저 세운 뒤 검증한 결과(docs/46), H13-H15는 그 결론으로 모델을 실제로 고친 뒤 다시 검증한 결과(docs/47), H1-1~H3-1은 H1-H3에 대한 외부 검토 의견을 받아 세운 후속 가설(docs/48, 부모 가설 바로 아래)이고, H1만 매번 실시간으로 다시 계산됩니다.
        </div>

        {error && <p className="panel-copy">{error}</p>}
        {!records && !error && <p className="panel-copy">불러오는 중…</p>}

        {records && (
          <div className="lab-hypothesis-list">
            {records.map((h) => (
              <div key={h.id} className="disorder-group lab-hypothesis-card">
                <div className="lab-hypothesis-header">
                  <small>{h.title}</small>
                  <span className={`lab-verdict-badge ${h.verdict}`}>{VERDICT_LABEL[h.verdict]}</span>
                </div>
                <p className="lab-hypothesis-statement">{h.statement}</p>
                <p className="lab-hypothesis-field">
                  <b>방법</b> {h.method}
                </p>
                <p className="lab-hypothesis-field">
                  <b>결과</b> {h.result_summary}
                </p>
                {h.raw_data_note && (
                  <p className="lab-hypothesis-raw">
                    <b>원자료</b> {h.raw_data_note}
                  </p>
                )}
                {h.evidence.length > 0 && (
                  <div className="lab-citation-list">
                    {h.evidence.map((e) => (
                      <a key={e.url} href={e.url} target="_blank" rel="noopener noreferrer" className="lab-citation-link">
                        {e.title}
                      </a>
                    ))}
                  </div>
                )}
                <p className="lab-hypothesis-meta">
                  {h.is_live_computed ? "매 요청마다 실시간 재계산됨" : `${h.executed_at} 실제 실행 기록`}
                </p>
              </div>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
