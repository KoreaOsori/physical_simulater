"use client";

import { useMemo, useState } from "react";
import Link from "next/link";

import { CHART_COLORS, LoopCharts, StatsPanel } from "@/features/virtual-organism/components/LoopCharts";
import { OrganismStage, type ControlMode } from "@/features/virtual-organism/components/OrganismStage";
import { useClosedLoop, type ClosedLoopApi } from "@/features/virtual-organism/lib/use-closed-loop";
import { useOrganismKeys } from "@/features/virtual-organism/lib/use-organism-keys";
import { usePilot, type PilotConfig } from "@/features/virtual-organism/lib/use-pilot";
import {
  fetchVirtualWormState,
  postVirtualOrganismPose,
  postVirtualOrganismSource,
  postVirtualWormReset,
  postVirtualWormStep,
} from "@/shared/lib/api-client";
import type { VirtualWormState, VirtualWormTick } from "@/types/lab";

const SENSORY_BAR_MAX = 20; // 시각화용 상한 -- 이 정도면 이 회로에서 뚜렷한 반응으로 관찰됨(실제 스파이크 수는 상한 없음)

const WORM_API: ClosedLoopApi<VirtualWormState, VirtualWormTick> = {
  fetchState: fetchVirtualWormState,
  reset: postVirtualWormReset,
  step: postVirtualWormStep,
  setSource: (x, y) => postVirtualOrganismSource("worm", x, y) as Promise<VirtualWormState>,
  setPose: (pose) => postVirtualOrganismPose("worm", pose) as Promise<VirtualWormState>,
  reorientEvent: "pirouette",
  label: "virtual worm",
};

/** 수동 조종 파라미터(docs/45). 속도는 docs/22에서 이미 검증한 실측 296μm/s(Fang-Yen
 * et al. 2010). 회전율·반사 지속시간은 손튜닝(기어가며 방향을 트는 속도, pirouette가
 * 수 초 걸리는 정성적 사실만 반영). 웜은 날 수 없다. */
const WORM_PILOT: PilotConfig = {
  walkSpeedUmS: 296,
  flySpeedUmS: null,
  climbUmS: 0,
  sinkUmS: 0,
  walkTurnRadS: 0.9,
  flyTurnRadS: 0,
  arenaRadiusUm: 45000,
  ceilingUm: 0,
  pathSpacingUm: 25,
  reflexBioMs: 2000,
};
const WORM_TIME_SCALES = [1, 5, 20];

/** 연구소(Lab) — 가상 예쁜꼬마선충 폐루프 환경 (docs/41). 실제 302개 뉴런 커넥톰이
 * 유인물질 농도 기울기를 감각으로 받아들이고, 그 결과로 실제로 이동하고, 이동한 새
 * 위치가 다시 감각 입력이 되는 순환(klinokinesis — 농도 감소 시 반전+재정향 빈도 증가).
 *
 * docs/44: 나침반 / 3D 실험실 두 보기. docs/45: 수동 조종을 실시간 이동으로 재설계
 * (W 전진·방향키 시선), 냄새원 옮기기, 반사 반응 허용(공동 조종), 기록 그래프·통계, 배속. */
export function LabVirtualWormPage() {
  const [mode, setMode] = useState<ControlMode>("auto");
  const [timeScale, setTimeScale] = useState(1);
  const [allowReflex, setAllowReflex] = useState(false);
  const { keysRef, pressed } = useOrganismKeys();
  const pilot = usePilot(mode === "manual", WORM_PILOT, keysRef, timeScale);
  const { state, recentTicks, history, loading, playing, setPlaying, error, motion, lastStepMs, reconnecting, reset, stepBatch, moveSource, commitPose } =
    useClosedLoop(WORM_API, { manual: mode === "manual", pilot, allowReflex });

  const changeMode = async (m: ControlMode) => {
    if (m === mode) return;
    if (m === "manual") {
      setPlaying(false);
      if (state) pilot.init(state);
      setMode("manual");
    } else {
      setMode("auto");
      await commitPose(pilot.takeSync());
    }
  };

  const lastTick = recentTicks[0] ?? null;
  const manualTick = lastTick?.control === "manual";
  const manual = mode === "manual";

  const chartRows = useMemo(
    () => ({
      c: history.map((t) => ({ x: t.bio_time_s, ys: [t.concentration], marked: t.event === "pirouette", manual: t.control === "manual" })),
      n: history.map((t) => ({ x: t.bio_time_s, ys: [t.forward_spikes, t.reverse_spikes], marked: t.event === "pirouette", manual: t.control === "manual" })),
    }),
    [history],
  );

  return (
    <main className="lab-shell">
      <header className="topbar">
        <div className="brand">
          <b>∿</b> 신경 / <strong>연구소</strong>
          <i>β</i>
        </div>
        <div className="specimen-title">
          <span>탐구</span>
          <strong>가상 예쁜꼬마선충 — 환경 폐루프</strong>
          <em>실제 302개 뉴런 커넥톰 · klinokinesis</em>
        </div>
        <div className="top-status">
          <Link href="/lab/virtual-fly" className="species-switch">
            초파리 폐루프
          </Link>
          <Link href="/lab" className="species-switch">
            ← 연구소
          </Link>
        </div>
      </header>
      <section className="lab-content">
        <div className="lab-honesty-banner">
          {state?.honesty_note ??
            "이것은 실제 관찰이 아니라 이 프로젝트의 시뮬레이션입니다 — 실제 302개 뉴런 커넥톰(Brian2 HH 모델)으로 klinokinesis(농도 감소 시 반전+재정향 빈도 증가) 메커니즘만 구현했고, klinotaxis(정밀 조향)는 이번 범위에 포함되지 않았습니다."}{" "}
          3D 웜·플레이트는 코드로 만든 도식적 모델이며(실제 비율), 몸의 굽이 파동은 실제 이동 거리에 맞춰 움직이는 표현입니다.
        </div>

        {!state && !error && <p className="panel-copy">가상 웜 환경을 불러오는 중…</p>}
        {error && <p className="panel-copy vo-error">{error}</p>}

        {state && motion && (
          <>
            <OrganismStage
              species="worm"
              state={state}
              motion={motion}
              mode={mode}
              onModeChange={(m) => void changeMode(m)}
              keysRef={keysRef}
              pressed={pressed}
              pilotRef={pilot.pilotRef}
              statusLabel={
                manual ? (pressed.forward ? "수동 전진" : "수동 · 정지") : !lastTick ? "대기 중" : lastTick.event === "run" ? "직진 (run)" : "반전+재정향 (pirouette)"
              }
              statusTone={lastTick?.event === "pirouette" ? "alert" : "calm"}
              brainNote={
                manualTick && lastTick
                  ? `뇌의 결정: ${lastTick.event === "run" ? "직진 유지" : "반전+재정향"} (AVB ${lastTick.forward_spikes} / AVA ${lastTick.reverse_spikes})${
                      lastTick.event === "pirouette" ? (allowReflex ? " — 반사 실행됨" : " — 반사 꺼짐, 이동엔 미적용") : ""
                    }`
                  : null
              }
              fieldColor="#7fdc7f"
              sourceColor="#e0b48c"
              lastStepMs={lastStepMs}
              reconnecting={reconnecting}
              timeScale={timeScale}
              timeScaleOptions={WORM_TIME_SCALES}
              onTimeScale={setTimeScale}
              allowReflex={allowReflex}
              onAllowReflex={setAllowReflex}
              onPlaceSource={(x, y) => void moveSource(x, y)}
            />

            <div className="lab-experiment-layout">
              <div className="lab-experiment-picker">
                <div className="worm-arena-controls">
                  <button type="button" onClick={() => void reset()} disabled={loading || playing}>
                    다시 시작
                  </button>
                  <button type="button" onClick={() => void stepBatch(1)} disabled={loading || playing || manual}>
                    1틱 진행
                  </button>
                  <button type="button" onClick={() => void stepBatch(10)} disabled={loading || playing || manual}>
                    10틱 진행
                  </button>
                  <button type="button" aria-pressed={playing} onClick={() => setPlaying((p) => !p)} disabled={(loading && !playing) || manual}>
                    {playing ? "자동 재생 중지" : "자동 재생"}
                  </button>
                </div>
                <p className="panel-copy">
                  틱당 100ms 생물학적 시간(실제 Brian2 연산 비용 때문에 실시간이 아니라 배치로 진행) · 전진 속도
                  296μm/s(Fang-Yen et al. 2010 실측 범위, docs/22에서 이미 검증한 값 재사용).
                </p>
                {manual && (
                  <p className="panel-copy">
                    수동 조종: 방향키로 카메라 시선을 돌리고 W를 누르고 있으면 웜이 그쪽으로 몸을 돌리며 실측 속도로 기어갑니다(배속은
                    생물학적 시간 기준). 후진·옆걸음 키는 없습니다 — 후진(pirouette)은 뇌가 결정하는 고유 행동입니다. 뇌(302개
                    뉴런)는 지금 위치를 계속 따라가며 계산되고, &lsquo;반사 반응 허용&rsquo;을 켜면 뇌가 반전을 결정하는 순간 실제로
                    몸이 반전합니다. 광원에서 약 5~55mm 구간에서 광원 반대쪽으로 기어가면 AWC/ASER가 실제로 발화하고, 그보다
                    멀거나 가까우면 기울기가 문턱보다 약해 느끼지 못합니다(docs/46·47에서 직접 측정). 출발점(40mm)은 이 구간
                    안이고, 웜은 일부러 광원 반대쪽을 보고 출발합니다 — 광원에 가려면 뇌가 농도 감소를 느껴 돌아서야 합니다.
                  </p>
                )}
                <StatsPanel stats={state.stats} reachLabel="광원 도달 시각" />
              </div>

              <div className="lab-experiment-result">
                <div className="lab-metrics-grid">
                  <div className="lab-metric">
                    <strong>{state.tick}</strong>
                    <span>진행된 틱</span>
                  </div>
                  <div className="lab-metric">
                    <strong>{state.concentration.toFixed(3)}</strong>
                    <span>현재 위치 농도(0-1)</span>
                  </div>
                  <div className="lab-metric">
                    <strong>{state.heading_deg.toFixed(0)}°</strong>
                    <span>현재 진행 방향</span>
                  </div>
                  <div className="lab-metric">
                    <strong>{state.reached_source ? "도달" : "탐색 중"}</strong>
                    <span>유인물질 광원</span>
                    {state.reached_source && <em>실제로 광원 근처(체장 몇 배 이내)에 도착했습니다</em>}
                  </div>
                </div>

                <LoopCharts
                  concentrationRows={chartRows.c}
                  neuronRows={chartRows.n}
                  neuronSeries={[
                    { name: "AVB 전진", color: CHART_COLORS[0] },
                    { name: "AVA 후진", color: CHART_COLORS[1] },
                  ]}
                  neuronTitle="명령 인터뉴런 발화 수 (틱당)"
                  markLabel="뇌가 반전+재정향 결정"
                />

                {lastTick && (
                  <div className="disorder-group">
                    <small>가장 최근 틱의 실제 신경 활동{manualTick ? " (수동 조종 중)" : ""}</small>
                    <div className="worm-arena-controls" style={{ marginBottom: 6 }}>
                      <span className={`worm-event-badge ${lastTick.event}`}>{lastTick.event === "run" ? "run (직진 유지)" : "pirouette (반전+재정향)"}</span>
                      <span className="panel-copy" style={{ margin: 0 }}>
                        AVB(전진) {lastTick.forward_spikes}회 · AVA(후진) {lastTick.reverse_spikes}회 · ΔC(틱당){" "}
                        {lastTick.delta_concentration >= 0 ? "+" : ""}
                        {lastTick.delta_concentration.toFixed(6)}
                      </span>
                    </div>
                    <div className="worm-sensory-bars">
                      {lastTick.sensory_activity.map((s) => (
                        <div key={s.neuron_id} className="worm-sensory-bar-row">
                          <span>{s.neuron_id}</span>
                          <span className="worm-sensory-bar-track">
                            <span className="worm-sensory-bar-fill" style={{ width: `${Math.min(100, (s.spike_count / SENSORY_BAR_MAX) * 100)}%` }} />
                          </span>
                          <span>{s.spike_count}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <div className="disorder-group">
                  <small>최근 틱 로그 ({recentTicks.length}개, 최신순)</small>
                  <div className="lab-event-log">
                    {recentTicks.map((t) => (
                      <div key={t.tick} className="lab-event-row">
                        <span className="lab-candidate-score">#{t.tick}</span>
                        <span className={`worm-event-badge ${t.event}`}>{t.event}</span>
                        <span>
                          {t.bio_time_s.toFixed(1)}s · C={t.concentration.toFixed(3)} · fwd {t.forward_spikes} / rev {t.reverse_spikes}
                          {t.control === "manual" ? " · 수동" : ""}
                          {t.reached_source ? " · 도달" : ""}
                        </span>
                      </div>
                    ))}
                    {recentTicks.length === 0 && <p className="panel-copy">아직 진행된 틱이 없습니다 — 위에서 진행해보세요.</p>}
                  </div>
                </div>
              </div>
            </div>
          </>
        )}
      </section>
    </main>
  );
}
