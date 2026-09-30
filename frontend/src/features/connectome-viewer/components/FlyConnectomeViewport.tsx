"use client";

import { useState } from "react";

import { DiveRevealSlider } from "@/features/connectome-viewer/components/DiveRevealSlider";
import { FlyConnectomeCanvas } from "@/features/connectome-viewer/components/FlyConnectomeCanvas";
import { diveStageLabel, FLY_DIVE_CONFIG } from "@/features/connectome-viewer/lib/fly-dive-stages";
import { FLY_CIRCUITS, type FlyCircuit } from "@/features/lab-shell/lib/fly-circuits";
import { useFlySimulationStore } from "@/store/fly-simulation-store";

interface FlyConnectomeViewportProps {
  circuit: FlyCircuit;
}

export function FlyConnectomeViewport({ circuit }: FlyConnectomeViewportProps) {
  const connectome = useFlySimulationStore((s) => s.connectome);
  const { legend } = FLY_CIRCUITS[circuit];
  const [showAnatomy, setShowAnatomy] = useState(true);
  const diveConfig = FLY_DIVE_CONFIG[circuit] ?? null;
  // Pages with a dive stage start at the external organ (겉모습) — the
  // familiar starting point the user asked for — and drag inward from
  // there; pages without one (navigation) just show the network as before.
  const [diveProgress, setDiveProgress] = useState(diveConfig ? 0 : 1);

  return (
    <section className="viewport">
      <div className="view-meta">
        <span>모델 뷰 / 3D · 드래그로 회전, 스크롤로 확대</span>
        <span>
          {connectome
            ? `뉴런 ${connectome.neuron_count_total} · 시냅스 ${connectome.synapses.length}`
            : "로딩 중"}
        </span>
      </div>
      {diveConfig && (
        <DiveRevealSlider
          progress={diveProgress}
          onChange={setDiveProgress}
          stageLabel={diveStageLabel(diveProgress)}
          stops={[diveConfig.organLabel, "감각기관", "신경계"]}
        />
      )}
      <button
        type="button"
        className="anatomy-toggle"
        onClick={() => setShowAnatomy((v) => !v)}
        aria-pressed={showAnatomy}
      >
        해부 영역 {showAnatomy ? "숨기기" : "표시"}
      </button>
      <div className="scanlines" />
      <FlyConnectomeCanvas showAnatomy={showAnatomy} diveProgress={diveProgress} diveConfig={diveConfig} />
      <div className="legend">
        {legend.map(({ color, label }) => (
          <span key={label}><i style={{ background: color }} />{label}</span>
        ))}
      </div>
    </section>
  );
}
