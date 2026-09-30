"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { DiveRevealSlider } from "@/features/connectome-viewer/components/DiveRevealSlider";
import { HumanMicroCanvas } from "@/features/connectome-viewer/components/HumanMicroCanvas";
import { humanDiveStageLabel } from "@/features/connectome-viewer/lib/human-dive-stages";
import { fetchHumanMacroConnectome, fetchHumanMicroSample } from "@/shared/lib/api-client";
import type { HeadAnatomy, MicroConnectomeSample } from "@/types/human";

export function HumanMicroPage() {
  const [sample, setSample] = useState<MicroConnectomeSample | null>(null);
  const [anatomy, setAnatomy] = useState<HeadAnatomy | null>(null);
  const [diveProgress, setDiveProgress] = useState(0);
  const [showSynapses, setShowSynapses] = useState(true);

  useEffect(() => {
    fetchHumanMicroSample()
      .then(setSample)
      .catch((error: unknown) => console.error("Failed to load human micro sample", error));
    // Reuses the macro connectome's real MNI anatomy layers as generic
    // context for this page's dive-in reveal (see HumanMicroCanvas) —
    // not a second copy of the data, just the same response's `anatomy` field.
    fetchHumanMacroConnectome()
      .then((c) => setAnatomy(c.anatomy))
      .catch((error: unknown) => console.error("Failed to load human head anatomy", error));
  }, []);

  return (
    <main className="lab-shell">
      <header className="topbar">
        <div className="brand">
          <b>∿</b> 신경 / <strong>인간 연구소</strong>
          <i>β</i>
        </div>
        <div className="specimen-title">
          <span>표본</span>
          <strong>인간 / 미시 피질 샘플 (측두엽)</strong>
          <em>H01 · 실제 EM 재구성 뉴런 104개</em>
        </div>
        <div className="top-status">
          <Link href="/human/connectome" className="species-switch">
            ↑ 커넥톰 목록
          </Link>
        </div>
      </header>
      <section className="viewport">
        <div className="view-meta">
          <span>모델 뷰 / 3D · 드래그로 회전, 스크롤로 확대</span>
          <span>
            {sample
              ? `뉴런 ${sample.neuron_count_total} · 점 ${sample.point_count_total.toLocaleString()} · 시냅스 ${sample.synapse_count_total.toLocaleString()}`
              : "로딩 중"}
          </span>
        </div>
        <DiveRevealSlider
          progress={diveProgress}
          onChange={setDiveProgress}
          stageLabel={humanDiveStageLabel(diveProgress)}
          stops={["겉모습", "뇌 조직", "신경계(실제 뉴런)"]}
        />
        {sample && sample.synapse_count_total > 0 && (
          <button
            type="button"
            className="anatomy-toggle"
            onClick={() => setShowSynapses((v) => !v)}
            aria-pressed={showSynapses}
          >
            시냅스 접촉점 {showSynapses ? "숨기기" : "표시"}
          </button>
        )}
        <div className="scanlines" />
        <HumanMicroCanvas sample={sample} anatomy={anatomy} diveProgress={diveProgress} showSynapses={showSynapses} />
        <div className="legend">
          <span>실제 재구성 뉴런 104개 — 뉴런별 색상 구분, 100:1 다운샘플링</span>
          <span>간질 수술 접근 경로의 인간 측두엽 조직 ~1mm³</span>
          <span><i style={{ background: "rgb(255,140,51)" }} />시냅스 · 이 뉴런이 보내는 쪽(AXON)</span>
          <span><i style={{ background: "rgb(89,166,255)" }} />시냅스 · 이 뉴런이 받는 쪽(DENDRITE)</span>
          <span>반대편은 대부분 미검수 세그먼트(회로도 아님 — SOURCES.md 참고)</span>
          <span>겉모습·뇌 조직 단계는 일반 MNI 평균 템플릿(이 샘플에 정합된 좌표 아님)</span>
        </div>
      </section>
    </main>
  );
}
