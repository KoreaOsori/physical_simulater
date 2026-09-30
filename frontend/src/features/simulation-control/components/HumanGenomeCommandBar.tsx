"use client";

import { useCallback } from "react";

import { postGenomeCommand } from "@/shared/lib/api-client";
import { useHumanGenomeStore } from "@/store/human-genome-store";

interface HumanGenomeCommandBarProps {
  filter: string;
  onFilterChange: (filter: string) => void;
  counts: Record<string, number>;
}

const FILTERS: { key: string; label: string }[] = [
  { key: "all", label: "전체" },
  { key: "nervous_system_development", label: "신경계 발달" },
  { key: "chemical_synaptic_transmission", label: "시냅스 전달" },
  { key: "visual_perception", label: "시각 지각" },
];

const COMMAND_LABEL: Record<string, string> = {
  BDNF_ACTIVATION: "BDNF 경로 실행 중",
  ARC_PLASTICITY_ACTIVATION: "Arc/Arg3.1 경로 실행 중",
};

const COMMAND_SUBTITLE: Record<string, string> = {
  BDNF_ACTIVATION: "신경 활동 → CREB 인산화 → BDNF 발현 → TrkB 결합 → 시냅스 가소성",
  ARC_PLASTICITY_ACTIVATION: "NMDA 수용체 활성화 → CaMKII 인산화 → Arc/Arg3.1 발현 → 시냅스 가소성",
};

/** Functional filter (real GO-tag membership, see SOURCES.md) + the real
 * documented gene-expression cascades this pass implements (BDNF, and
 * Arc/Arg3.1 added in v4 — docs/28). No natural keyboard mapping for
 * either, same reasoning as FlyCommandBar. */
export function HumanGenomeCommandBar({ filter, onFilterChange, counts }: HumanGenomeCommandBarProps) {
  const activeCommand = useHumanGenomeStore((s) => s.activeCommand);
  const signalActive = useHumanGenomeStore((s) => s.signalActive);

  const sendBdnf = useCallback(() => {
    postGenomeCommand("BDNF_ACTIVATION").catch((error: unknown) => console.error("Failed to send genome command", error));
  }, []);
  const sendArc = useCallback(() => {
    postGenomeCommand("ARC_PLASTICITY_ACTIVATION").catch((error: unknown) => console.error("Failed to send genome command", error));
  }, []);

  return (
    <footer className="control-deck">
      <div className="sequence">
        <small>02 / 기능 필터 · 경로 자극</small>
        <strong>{activeCommand === null ? "대기 중" : (COMMAND_LABEL[activeCommand] ?? "경로 실행 중")}</strong>
        <p>{activeCommand === null ? "자극할 경로를 선택하세요" : COMMAND_SUBTITLE[activeCommand]}</p>
      </div>
      <div className="odor-buttons">
        {FILTERS.map(({ key, label }) => (
          <button
            key={key}
            type="button"
            onClick={() => onFilterChange(key)}
            className={filter === key ? "lit" : undefined}
          >
            {label} ({counts[key] ?? 0})
          </button>
        ))}
        <button type="button" disabled={signalActive} onClick={sendBdnf} className={signalActive ? "lit" : undefined}>
          BDNF 활동의존적 발현 자극
        </button>
        <button type="button" disabled={signalActive} onClick={sendArc} className={signalActive ? "lit" : undefined}>
          Arc/Arg3.1 시냅스 가소성 자극
        </button>
      </div>
    </footer>
  );
}
