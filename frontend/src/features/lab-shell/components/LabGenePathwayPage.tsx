"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { fetchLabGenePathwayCandidates } from "@/shared/lib/api-client";
import type { GenePathwayReport } from "@/types/lab";

/** 연구소(Lab) — 유전자 경로 후보 가설 탐색기 (docs/37). 실제 염색체
 * 위치(cytoband) 데이터로 "위치 후보 유전자(positional candidate gene)"
 * 접근 — 실제 유전학 방법론 — 을 이 프로젝트의 2개 기존 경로(BDNF,
 * Arc/Arg3.1)에 적용해, 물리적으로 가까운 실제 유전자 후보를 찾는다. */
export function LabGenePathwayPage() {
  const [reports, setReports] = useState<GenePathwayReport[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchLabGenePathwayCandidates()
      .then(setReports)
      .catch((err: unknown) => {
        console.error("Failed to load gene pathway candidates", err);
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
          <strong>유전자 경로 후보 가설 탐색기</strong>
          <em>위치 후보 유전자 접근</em>
        </div>
        <div className="top-status">
          <Link href="/lab" className="species-switch">
            ← 연구소
          </Link>
        </div>
      </header>
      <section className="lab-content">
        <div className="lab-honesty-banner">
          물리적으로 가깝다는 것이 기능적으로 연관됐다는 뜻은 아닙니다 — 유전자 클러스터·공동조절의 실제 사례가
          있지만(예: HOX 클러스터), 이웃한다고 반드시 관련 있는 건 아닙니다. 이 목록은 후보를 좁혀보는
          가설이지, 새로운 경로를 발견했다는 주장이 아닙니다.
        </div>

        {error && <p className="panel-copy">{error}</p>}
        {!reports && !error && <p className="panel-copy">불러오는 중…</p>}

        {reports && (
          <div className="lab-gene-report-grid">
            {reports.map((report) => (
              <div key={report.seed_symbol} className="disorder-group lab-gene-report">
                <small>
                  {report.seed_symbol} ({report.pathway_label}) — {report.seed_chromosome}번 염색체 {report.seed_map_location}
                </small>
                {report.candidates.length === 0 ? (
                  <p className="panel-copy">같은 염색체에서 실제 위치가 확인된 후보를 찾지 못했습니다.</p>
                ) : (
                  <div className="lab-neuron-groups">
                    {report.candidates.map((c) => (
                      <div key={c.symbol} className="lab-gene-candidate">
                        <div className="lab-gene-candidate-header">
                          <strong>{c.symbol}</strong>
                          <span className="lab-candidate-score">{c.map_location} · 거리 {c.distance_fraction.toFixed(4)}</span>
                        </div>
                        {c.description && <p className="lab-gene-candidate-desc">{c.description}</p>}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
