"use client";

import { useEffect, useState } from "react";

import { fetchClassicAblations } from "@/shared/lib/api-client";
import { useSimulationStore } from "@/store/simulation-store";
import type { ClassicAblation } from "@/types/connectome";

const CATEGORY_LABEL: Record<string, string> = {
  locomotion: "운동",
  sensory: "감각",
  reproductive: "생식",
};

/** Same accordion pattern as HumanMacroPage's disorder list (docs/21) one
 * level down: real laser-ablation studies instead of clinical lesion
 * syndromes. Toggling an entry on (1) highlights its neurons red in the 3D
 * scene (ConnectomeCanvas's `silenced` prop) and (2) makes the NEXT command
 * sent via the normal keyboard controls silence those neurons' outputs
 * (useSendCommand.ts reads `activeAblation` from the store) — no separate
 * "run" button, since this project avoids on-screen controls that duplicate
 * the existing keyboard command path. */
export function AblationPanel() {
  const [ablations, setAblations] = useState<ClassicAblation[]>([]);
  const activeAblation = useSimulationStore((s) => s.activeAblation);
  const setActiveAblation = useSimulationStore((s) => s.setActiveAblation);

  useEffect(() => {
    fetchClassicAblations()
      .then(setAblations)
      .catch((error: unknown) => console.error("Failed to load classic ablations", error));
  }, []);

  if (ablations.length === 0) return null;

  return (
    <div className="ablation-panel">
      <small>고전적 절제(ablation) 연구</small>
      <p className="panel-copy">
        선택하면 해당 뉴런이 3D 씬에서 빨갛게 표시되고, 이후 키보드 명령(↑↓←→ 등)의 출력이 그 뉴런에서 억제된 상태로
        전송됩니다 — 실제 세포 제거가 아니라 출력 시냅스 무효화로 근사한 것입니다.
      </p>
      <div className="ablation-list">
        {ablations.map((ablation) => {
          const isActive = activeAblation?.name === ablation.name;
          return (
            <div key={ablation.name} className="ablation-item">
              <button
                type="button"
                aria-pressed={isActive}
                onClick={() => setActiveAblation(isActive ? null : ablation)}
              >
                <small>{CATEGORY_LABEL[ablation.category] ?? ablation.category}</small>
                {ablation.name}
              </button>
              {isActive && (
                <p className="ablation-detail">
                  {ablation.description}
                  <br />
                  <em>절제 대상: {ablation.neuron_ids.join(", ")}</em>
                </p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
