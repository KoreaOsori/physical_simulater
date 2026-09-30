"use client";

import { useKeyboardCommands } from "@/features/simulation-control/hooks/useKeyboardCommands";
import { useSendCommand } from "@/features/simulation-control/hooks/useSendCommand";
import { useSimulationStore } from "@/store/simulation-store";

const SEQUENCE_STEPS = ["명령", "AVB / PVC", "ACh", "근육", "운동"];

/**
 * Bottom status bar showing the current command's stage progress. All actual
 * commands are issued via the keyboard (see useKeyboardCommands) or the
 * tissue panel's "시퀀스 재생" button — there is no on-screen direction pad,
 * since one would just duplicate the keyboard controls while eating layout space.
 */
export function SequenceStatusBar() {
  const sendCommand = useSendCommand();
  const activeCommand = useSimulationStore((s) => s.activeCommand);
  const signalActive = useSimulationStore((s) => s.signalActive);
  const habituationLevel = useSimulationStore((s) => s.habituationLevel);

  useKeyboardCommands(sendCommand);

  return (
    <footer className="control-deck">
      <div className="sequence">
        <small>02 / 운동 명령</small>
        <strong>{activeCommand === null ? "대기 중" : "신호 시퀀스 실행"}</strong>
        <p>입력 → 시냅스 → 신경전달물질 → 근육 수축 → 운동</p>
      </div>
      <div className="sequence-map">
        {SEQUENCE_STEPS.map((step, i) => (
          <span key={step} className={signalActive ? "contents lit" : "contents"}>
            {i > 0 && <i />}
            <span className={signalActive ? "lit" : ""}>{step}</span>
          </span>
        ))}
      </div>
      <div className="scenario">
        <small>실험 상황</small>
        <button type="button">이동 <b>⌄</b></button>
      </div>
      {habituationLevel > 0.01 && (
        <div className="habituation-readout" title="반복 자극으로 자극 뉴런 출력 시냅스가 얼마나 약해졌는지 — 시간이 지나면 자연 회복(Rankin et al. 1990/2009)">
          <small>습관화</small>
          <strong>{habituationLevel.toLocaleString("ko-KR", { style: "percent", maximumFractionDigits: 0 })}</strong>
        </div>
      )}
    </footer>
  );
}
