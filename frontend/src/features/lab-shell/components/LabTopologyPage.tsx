"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { fetchLabTopologyReport, fetchLabTopologySpecies } from "@/shared/lib/api-client";
import type { TopologyReport } from "@/types/lab";

const SPECIES_LABEL: Record<string, string> = {
  c_elegans: "예쁜꼬마선충 (전체 신경계)",
  drosophila_olfactory: "초파리 — 후각 회로",
  drosophila_visual: "초파리 — 시각 회로",
  drosophila_navigation: "초파리 — 항법 회로",
  human_macro: "인간 — 거시 구조연결",
};

/** 연구소(Lab) — 네트워크 위상 분석 (docs/34). 이 프로젝트가 이미 가진 실제
 * 커넥톰 그래프에 표준 네트워크 과학 지표를 계산해 "위상적으로 흥미롭지만
 * 아직 이 프로젝트의 큐레이션 문헌엔 없는" 후보를 알고리즘으로 찾아본다 —
 * 실제 데이터로부터 나온 진짜 숫자지만, 해석은 검증된 사실이 아니라
 * 가설이라는 걸 배너로 항상 고정 표시한다. */
export function LabTopologyPage() {
  const [speciesIds, setSpeciesIds] = useState<string[]>([]);
  const [activeSpecies, setActiveSpecies] = useState<string | null>(null);
  const [report, setReport] = useState<TopologyReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchLabTopologySpecies()
      .then((ids) => {
        setSpeciesIds(ids);
        setActiveSpecies(ids[0] ?? null);
      })
      .catch((err: unknown) => console.error("Failed to load lab topology species list", err));
  }, []);

  // 로딩 상태를 별도 state로 안 두고 report/activeSpecies 불일치로부터
  // 도출한다(react-hooks/set-state-in-effect가 effect 본문에서의 동기
  // setState를 금지 -- 이 프로젝트 다른 페이지들(FlyLabPage.tsx 등)의
  // fetch-on-param-change 패턴과 같은 이유로 콜백 안에서만 setState).
  const isLoading = activeSpecies !== null && error === null && (report === null || report.species_id !== activeSpecies);

  useEffect(() => {
    if (!activeSpecies) return;
    // 실제 버그: 느린 종(초파리 회로, 최대 86초)을 고른 직후 바로 빠른
    // 종으로 바꾸면, 먼저 고른 느린 요청이 나중에 응답으로 돌아와서
    // 이미 표시된 새 종의 결과를 조용히 덮어써버렸다(레이스 컨디션) --
    // 클린업에서 cancelled 플래그를 세워 stale 응답을 무시한다(React의
    // 표준 fetch-race-guard 패턴).
    let cancelled = false;
    fetchLabTopologyReport(activeSpecies)
      .then((r) => {
        if (cancelled) return;
        setReport(r);
        setError(null);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        console.error("Failed to load lab topology report", err);
        setError("불러오지 못했습니다 — 잠시 후 다시 시도해주세요.");
      });
    return () => {
      cancelled = true;
    };
  }, [activeSpecies]);

  return (
    <main className="lab-shell">
      <header className="topbar">
        <div className="brand">
          <b>∿</b> 신경 / <strong>연구소</strong>
          <i>β</i>
        </div>
        <div className="specimen-title">
          <span>탐구</span>
          <strong>네트워크 위상 분석</strong>
          <em>그래프 이론 기반 가설 생성</em>
        </div>
        <div className="top-status">
          <Link href="/lab" className="species-switch">
            ← 연구소
          </Link>
        </div>
      </header>
      <section className="lab-content">
        <div className="lab-honesty-banner">
          이 페이지의 모든 숫자는 이 프로젝트가 실제로 가진 커넥톰 데이터로부터 계산한 진짜 값입니다. 하지만
          &ldquo;위상적으로 중심적이다&rdquo;는 &ldquo;생물학적으로 중요하다&rdquo;는 뜻이 아니고, &ldquo;이 프로젝트의
          큐레이션 데이터에 없다&rdquo;는 것도 &ldquo;실제 문헌에 없다&rdquo;는 뜻이 아닙니다 — 이건 가설을 만들어보는
          도구지, 발견을 주장하는 도구가 아닙니다. 개인 로컬 탐구용입니다.
        </div>

        <div className="network-switch lab-species-switch">
          {speciesIds.map((id) => (
            <button key={id} type="button" aria-pressed={activeSpecies === id} onClick={() => setActiveSpecies(id)}>
              {SPECIES_LABEL[id] ?? id}
            </button>
          ))}
        </div>

        {isLoading && (
          <p className="panel-copy">
            계산 중입니다… (초파리 회로처럼 큰 그래프는 처음 계산할 때 최대 1분 정도 걸릴 수 있습니다 — 이후엔
            서버에 캐시되어 즉시 표시됩니다)
          </p>
        )}
        {error && <p className="panel-copy">{error}</p>}
        {report && !isLoading && report.species_id === activeSpecies && <TopologyReportView report={report} />}
      </section>
    </main>
  );
}

function TopologyReportView({ report }: { report: TopologyReport }) {
  return (
    <>
      <div className="lab-metrics-grid">
        <Metric label="노드" value={report.node_count.toLocaleString("ko-KR")} />
        <Metric label="엣지" value={report.edge_count.toLocaleString("ko-KR")} />
        <Metric label="밀도" value={report.density.toFixed(4)} />
        <Metric label="평균 군집계수" value={report.average_clustering.toFixed(4)} />
        <Metric
          label="평균 최단경로"
          value={report.average_shortest_path_length !== null ? report.average_shortest_path_length.toFixed(3) : "—"}
        />
        <Metric
          label="작은세상성(σ)"
          value={report.small_world_sigma !== null ? report.small_world_sigma.toFixed(3) : "계산 생략"}
          note={report.small_world_skipped_reason ?? (report.small_world_sigma !== null ? "σ > 1이면 작은세상 특성 시사(참고용)" : undefined)}
        />
        <Metric label="모듈성(Q)" value={report.modularity_q.toFixed(4)} note={`커뮤니티 ${report.community_sizes.length}개`} />
        <Metric label="연결 상태" value={report.is_fully_connected ? "하나로 연결됨" : "여러 조각으로 분리됨"} />
      </div>

      <div className="disorder-group lab-candidate-group">
        <small>
          위상적으로 흥미로운 후보 (중심성 종합 순위) — {report.curated_literature_note}
          {report.betweenness_is_approximate && " 그래프가 커서 매개중심성은 표준 샘플링 근사값입니다."}
        </small>
        <div className="lab-candidate-list">
          {report.top_candidates.map((c, i) => (
            <div key={c.node_id} className={`lab-candidate-item${c.already_in_curated_literature ? " curated" : ""}`}>
              <span className="lab-candidate-rank">{i + 1}</span>
              <span className="lab-candidate-name">{c.node_label}</span>
              <span className="lab-candidate-score">종합 {c.combined_score.toFixed(3)}</span>
              {c.already_in_curated_literature ? (
                <span className="lab-candidate-badge known">큐레이션됨</span>
              ) : (
                <span className="lab-candidate-badge candidate">미큐레이션 후보</span>
              )}
            </div>
          ))}
        </div>
      </div>
    </>
  );
}

function Metric({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="lab-metric">
      <strong>{value}</strong>
      <span>{label}</span>
      {note && <em>{note}</em>}
    </div>
  );
}
