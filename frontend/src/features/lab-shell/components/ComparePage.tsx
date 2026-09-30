"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { fetchCompareSummary } from "@/shared/lib/api-client";
import { SpeciesCompareChart, type CompareBar } from "@/features/species-compare/components/SpeciesCompareChart";
import type { CompareSummary } from "@/types/compare";

// Fixed categorical order/hues per species -- validated for dark-mode CVD
// separation (dataviz skill's scripts/validate_palette.js, surface #06100d):
// all three checks pass; assigned in this fixed order, never cycled/re-picked
// by a filter (bars are also always direct-labeled with the species name, so
// identity never depends on color alone).
const SPECIES_COLOR: Record<string, string> = {
  c_elegans: "#5fa832",
  drosophila: "#1f93c9",
  human: "#b8842a",
};

export function ComparePage() {
  const [summary, setSummary] = useState<CompareSummary | null>(null);

  useEffect(() => {
    fetchCompareSummary()
      .then(setSummary)
      .catch((error: unknown) => console.error("Failed to load compare summary", error));
  }, []);

  return (
    <main className="lab-shell compare-shell">
      <header className="topbar">
        <div className="brand">
          <b>∿</b> 신경 / <strong>종간 비교</strong>
          <i>β</i>
        </div>
        <div className="top-status">
          <Link href="/" className="species-switch">
            ← 예쁜꼬마선충
          </Link>
          <Link href="/fly" className="species-switch">
            초파리
          </Link>
          <Link href="/human" className="species-switch">
            인간
          </Link>
          <Link href="/lab" className="species-switch">
            연구소
          </Link>
        </div>
      </header>
      <section className="compare-content">
        {!summary ? (
          <p className="compare-loading">백엔드 연결 대기...</p>
        ) : (
          <SpeciesCompareSections summary={summary} />
        )}
      </section>
    </main>
  );
}

function SpeciesCompareSections({ summary }: { summary: CompareSummary }) {
  const neuronBars: CompareBar[] = summary.species.map((s) => ({
    id: s.species_id,
    label: s.common_name_ko,
    value: s.dataset_neuron_count ?? 0,
    color: SPECIES_COLOR[s.species_id],
    note: s.dataset_note,
  }));

  const synapseBars: CompareBar[] = summary.species.map((s) => ({
    id: s.species_id,
    label: s.common_name_ko,
    value: s.dataset_synapse_count ?? 0,
    color: SPECIES_COLOR[s.species_id],
    note: s.dataset_note,
  }));

  const realWorldBars: CompareBar[] = summary.species.map((s) => ({
    id: s.species_id,
    label: s.common_name_ko,
    value: s.real_world_neuron_count ?? 0,
    color: SPECIES_COLOR[s.species_id],
    note: s.real_world_neuron_count_note,
  }));

  return (
    <>
      <section className="compare-section">
        <h2>이 프로젝트가 실제로 가진 데이터</h2>
        <p className="compare-section-note">
          아래는 각 종 페이지가 실제로 로드하는 데이터셋의 크기다 — 인간의 경우 뉴런 단위 데이터는 H01 EM 샘플(측두피질의
          작은 일부, 104개)뿐이며, 거시 파셀(400개)은 뉴런이 아니라 영역 단위라 별도 표기한다.
        </p>
        <div className="compare-chart-row">
          <div>
            <h3>뉴런 수 (로그축)</h3>
            <SpeciesCompareChart bars={neuronBars} unit="개" />
          </div>
          <div>
            <h3>시냅스/접촉점 수 (로그축)</h3>
            <SpeciesCompareChart bars={synapseBars} unit="개" />
          </div>
        </div>
        <ul className="compare-region-note">
          {summary.species
            .filter((s) => s.dataset_region_count != null)
            .map((s) => (
              <li key={s.species_id}>
                <b style={{ color: SPECIES_COLOR[s.species_id] }}>{s.common_name_ko}</b>: 거시 파셀{" "}
                {s.dataset_region_count!.toLocaleString("ko-KR")}개 (뉴런 수와 합산 불가 — 영역 단위 데이터)
              </li>
            ))}
        </ul>
      </section>

      <section className="compare-section compare-section-reference">
        <h2>참고용 — 실제 생물학적 규모</h2>
        <p className="compare-section-note">
          위 &ldquo;이 프로젝트가 실제로 가진 데이터&rdquo;와 절대 같은 것이 아니다 — 실제 종이 가진 총 뉴런 수를 문헌
          인용과 함께 보여줄 뿐이며, 특히 인간의 경우 이 프로젝트 데이터(104개)와 실제 규모(860억 개)의 격차 자체가
          &ldquo;왜 인간 전체 뇌 커넥톰이 아직 존재하지 않는가&rdquo;를 보여주는 핵심 메시지다.
        </p>
        <SpeciesCompareChart bars={realWorldBars} unit="개" />
      </section>
    </>
  );
}
