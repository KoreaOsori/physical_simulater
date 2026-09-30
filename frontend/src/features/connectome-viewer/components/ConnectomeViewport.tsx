"use client";

import { ConnectomeCanvas } from "@/features/connectome-viewer/components/ConnectomeCanvas";
import { LayerControlPanel } from "@/features/connectome-viewer/components/LayerControlPanel";
import { useSimulationStore } from "@/store/simulation-store";

export function ConnectomeViewport() {
  const connectome = useSimulationStore((s) => s.connectome);

  return (
    <section className="viewport">
      <div className="view-meta">
        <span>모델 뷰 / 3D · 드래그로 회전, 스크롤로 확대</span>
        <span>
          {connectome
            ? `뉴런 ${connectome.neuron_count_total} · 근육/조직 ${connectome.effector_count_total} · 시냅스 ${connectome.synapses.length}`
            : "로딩 중"}
        </span>
      </div>
      <div className="scanlines" />
      <ConnectomeCanvas />
      <LayerControlPanel />
      <div className="legend">
        <span><i style={{ background: "#75cce9" }} />감각뉴런</span>
        <span><i style={{ background: "#baff71" }} />중간뉴런</span>
        <span><i style={{ background: "#ff9c73" }} />운동뉴런</span>
        <span><i style={{ background: "#e0715c" }} />근육</span>
      </div>
    </section>
  );
}
