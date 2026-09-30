"use client";

import type { CSSProperties } from "react";

import { AblationPanel } from "@/features/ablation-panel/components/AblationPanel";
import { ResearchTrendsPanel } from "@/features/research-trends/components/ResearchTrendsPanel";
import { tissues } from "@/features/tissue-panel/data/tissues";
import { useSendCommand } from "@/features/simulation-control/hooks/useSendCommand";
import { useSimulationStore } from "@/store/simulation-store";

export function TissuePanel() {
  const selectedTissueId = useSimulationStore((s) => s.selectedTissueId);
  const setSelectedTissueId = useSimulationStore((s) => s.setSelectedTissueId);
  const connectome = useSimulationStore((s) => s.connectome);
  const sendCommand = useSendCommand();

  const tissue = tissues.find((item) => item.id === selectedTissueId)!;

  return (
    <aside className="panel anatomy">
      <div className="panel-head">
        01 / 해부 구조 <button type="button">⌄</button>
      </div>
      <div className="anatomy-scroll">
        <section className="sequence-card">
          <small>신경-운동 시퀀스</small>
          <strong>대기 중</strong>
          <p>입력 → 시냅스 → 신경전달물질 → 근육 수축 → 운동</p>
          <button type="button" onClick={() => sendCommand("forward")}>
            시퀀스 재생 <b>→</b>
          </button>
        </section>
        <section className="key-guide">
          <span>키보드 제어</span>
          <p>
            <b>↑ ↓ ← →</b> 이동 · <b>Z</b> 먹기 · <b>X</b> 배설 · <b>C</b> 번식
          </p>
        </section>
        <p className="panel-copy">조직 레이어를 선택하면 모델의 해당 위치가 강조됩니다.</p>
        <div className="tissue-list">
          {tissues.map((item, index) => (
            <button
              key={item.id}
              type="button"
              onClick={() => setSelectedTissueId(item.id)}
              className={selectedTissueId === item.id ? "tissue selected" : "tissue"}
            >
              <small>0{index + 1}</small>
              <i style={{ backgroundColor: item.color }} />
              <span>
                <b>{item.label}</b>
                <em>{item.detail}</em>
              </span>
              <strong>↗</strong>
            </button>
          ))}
        </div>
        <div className="selection-card" style={{ "--tissue": tissue.color } as CSSProperties}>
          <small>선택한 영역</small>
          <strong>{tissue.label}</strong>
          <p>{tissue.description}</p>
          {tissue.planned && <em className="planned">실시간 시뮬레이션 연동 예정</em>}
          <button type="button">구조 데이터 보기 →</button>
        </div>
        <div className="data-note">
          <small>데이터 원본</small>
          <b>{connectome ? `OpenWorm 커넥톰 · ${connectome.organism}` : "백엔드 연결 대기"}</b>
          <p>
            {connectome
              ? `뉴런 ${connectome.neuron_count_total}개, 근육/조직 ${connectome.effector_count_total}개, 시냅스 ${connectome.synapses.length}개. 뉴런 위치는 EM 재구성 기반 실제 좌표(OpenWorm), 근육/조직 위치는 인접 뉴런 좌표에 앵커링한 근사치입니다. 좌측 상단 "해부 레이어" 슬라이더로 겉모습→근육→신경계를 순서대로 확인할 수 있습니다.`
              : "뉴런 주소, 시냅스, 활성 추적 데이터를 이 위치에 연결합니다."}
          </p>
        </div>
        <AblationPanel />
        <ResearchTrendsPanel />
      </div>
    </aside>
  );
}
