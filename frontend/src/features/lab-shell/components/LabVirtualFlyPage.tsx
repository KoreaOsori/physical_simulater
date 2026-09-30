"use client";

import { useMemo, useState } from "react";
import Link from "next/link";

import { CHART_COLORS, LoopCharts, StatsPanel } from "@/features/virtual-organism/components/LoopCharts";
import { OrganismStage, type ControlMode } from "@/features/virtual-organism/components/OrganismStage";
import { useClosedLoop, type ClosedLoopApi } from "@/features/virtual-organism/lib/use-closed-loop";
import { useOrganismKeys } from "@/features/virtual-organism/lib/use-organism-keys";
import { usePilot, type PilotConfig } from "@/features/virtual-organism/lib/use-pilot";
import {
  fetchVirtualFlyState,
  postVirtualFlyReset,
  postVirtualFlyStep,
  postVirtualOrganismPose,
  postVirtualOrganismSource,
} from "@/shared/lib/api-client";
import type { VirtualFlyState, VirtualFlyTick } from "@/types/lab";

const MBON_BAR_MAX = 20; // 시각화용 상한 -- 문턱을 넘으면 이 회로에서 관찰되는 전형적 MBON01 발화 범위(52-74)의 하한 근처

const FLY_API: ClosedLoopApi<VirtualFlyState, VirtualFlyTick> = {
  fetchState: fetchVirtualFlyState,
  reset: postVirtualFlyReset,
  step: postVirtualFlyStep,
  setSource: (x, y) => postVirtualOrganismSource("fly", x, y) as Promise<VirtualFlyState>,
  setPose: (pose) => postVirtualOrganismPose("fly", pose) as Promise<VirtualFlyState>,
  reorientEvent: "avoidance",
  label: "virtual fly",
};

/** 수동 조종 파라미터(docs/45). 실측: 보행 28mm/s(Mendes et al. 2013, eLife 2:e00231),
 * 자유비행 평균 0.15m/s(Fry, Rohrseitz, Straw & Dickinson 2009, J Exp Biol 212:1120).
 * 손튜닝: 상승·하강 속도, 회전율, 반사 지속시간, 챔버 높이. */
const FLY_PILOT_BASE: PilotConfig = {
  walkSpeedUmS: 28000,
  flySpeedUmS: 150000,
  climbUmS: 60000,
  sinkUmS: 35000,
  walkTurnRadS: 7,
  flyTurnRadS: 12,
  arenaRadiusUm: 30000,
  ceilingUm: 40000,
  pathSpacingUm: 400,
  reflexBioMs: 300,
};
const FLY_TIME_SCALES = [0.25, 0.5, 1];

/** 연구소(Lab) — 가상 초파리 폐루프 환경 (docs/42). 실제 초파리 후각 회로(hemibrain
 * ~2,452개 뉴런)와 실제 문헌(Aso et al. 2014)이 확인한 MBON01(y5B'2a)의 회피 유도 역할을
 * 그대로 따른다 — DA1(페로몬 cVA) 냄새가 짙어질수록 MBON01이 발화하고, 발화하면
 * 반전+재정향(회피)한다.
 *
 * docs/44: 나침반 / 3D 실험실. docs/45: 실시간 수동 조종(W 전진 · 방향키 시선 · Space
 * 비행), 비행 챔버, 냄새원 옮기기, 반사 반응 허용, 기록 그래프·통계, 배속. */
export function LabVirtualFlyPage() {
  const [mode, setMode] = useState<ControlMode>("auto");
  const [timeScale, setTimeScale] = useState(1);
  const [allowReflex, setAllowReflex] = useState(false);
  const { keysRef, pressed } = useOrganismKeys();
  const pilot = usePilot(mode === "manual", FLY_PILOT_BASE, keysRef, timeScale);
  const { state, recentTicks, history, loading, playing, setPlaying, error, motion, lastStepMs, reconnecting, reset, stepBatch, moveSource, commitPose } =
    useClosedLoop(FLY_API, { manual: mode === "manual", pilot, allowReflex });

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
      c: history.map((t) => ({ x: t.bio_time_s, ys: [t.concentration], marked: t.event === "avoidance", manual: t.control === "manual" })),
      n: history.map((t) => ({ x: t.bio_time_s, ys: [t.mbon01_spikes], marked: t.event === "avoidance", manual: t.control === "manual" })),
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
          <strong>가상 초파리 — 환경 폐루프</strong>
          <em>실제 hemibrain 후각 회로 · MBON 밸런스 회피</em>
        </div>
        <div className="top-status">
          <Link href="/lab/virtual-worm" className="species-switch">
            웜 폐루프
          </Link>
          <Link href="/lab" className="species-switch">
            ← 연구소
          </Link>
        </div>
      </header>
      <section className="lab-content">
        <div className="lab-honesty-banner">
          {state?.honesty_note ??
            "이것은 실제 관찰이 아니라 이 프로젝트의 시뮬레이션입니다 — 실제 초파리 후각 회로(hemibrain, Brian2 HH 모델)로 DA1(페로몬 cVA) → PN → KC → MBON01 경로만 구현했고, MBON01(y5B'2a) 활성화가 회피를 유도한다는 것만 Aso et al. 2014로 확인된 실제 근거입니다."}{" "}
          3D 초파리·챔버는 코드로 만든 도식적 모델이며(실제 비율), 다리의 삼각보행은 실제 이동 거리에 맞춰 움직이는 표현입니다. 비행은
          수동 조종에서만 가능합니다(이 회로 데이터엔 비행을 결정하는 뉴런이 없음).
        </div>

        {!state && !error && <p className="panel-copy">가상 초파리 환경을 불러오는 중…</p>}
        {error && <p className="panel-copy vo-error">{error}</p>}

        {state && motion && (
          <>
            <OrganismStage
              species="fly"
              state={state}
              motion={motion}
              mode={mode}
              onModeChange={(m) => void changeMode(m)}
              keysRef={keysRef}
              pressed={pressed}
              pilotRef={pilot.pilotRef}
              statusLabel={
                manual ? (pressed.fly ? "상승 중" : pressed.forward ? "수동 전진" : "수동 · 정지") : !lastTick ? "대기 중" : lastTick.event === "avoidance" ? "회피 (avoidance)" : "순항 (cruise)"
              }
              statusTone={lastTick?.event === "avoidance" ? "alert" : "calm"}
              brainNote={
                manualTick && lastTick
                  ? `뇌의 결정: ${lastTick.event === "avoidance" ? "회피" : "순항"} (MBON01 ${lastTick.mbon01_spikes}회, 냄새 농도 ${lastTick.concentration.toFixed(3)})${
                      lastTick.event === "avoidance" ? (allowReflex ? " — 반사 실행됨" : " — 반사 꺼짐, 이동엔 미적용") : ""
                    }`
                  : null
              }
              fieldColor="#e0b48c"
              sourceColor="#e0824c"
              lastStepMs={lastStepMs}
              reconnecting={reconnecting}
              timeScale={timeScale}
              timeScaleOptions={FLY_TIME_SCALES}
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
                  <button type="button" onClick={() => void stepBatch(5)} disabled={loading || playing || manual}>
                    5틱 진행
                  </button>
                  <button type="button" aria-pressed={playing} onClick={() => setPlaying((p) => !p)} disabled={(loading && !playing) || manual}>
                    {playing ? "자동 재생 중지" : "자동 재생"}
                  </button>
                </div>
                <p className="panel-copy">
                  틱당 100ms 생물학적 시간(이 회로는 ~2,452개 뉴런이라 웜보다 틱당 연산이 더 걸림) · 보행 속도
                  28mm/s(Mendes et al. 2013 실측 대표값) · 회피 방향은 직전보다 냄새가 짙어지는 중이었으면 반대로, 옅어지는
                  중이었으면 그대로 물러남(광원 위치는 모름 — 냄새의 시간 변화만 사용, docs/47).
                </p>
                {manual && (
                  <p className="panel-copy">
                    수동 조종: 방향키로 시선을 돌리고 W로 그쪽을 향해 걷습니다(28mm/s). Space를 누르고 있으면 날아올라 상승하고, 떼면
                    서서히 내려와 착지합니다 — 비행 중 W는 약 150mm/s(Fry et al. 2009 자유비행 평균)로 날아갑니다. 비행 중
                    냄새 농도는 바닥 여과지에서의 3D 거리로 계산돼, 냄새원 위를 높이 날면 실제 회로가 문턱을 넘지 않습니다.
                    &lsquo;반사 반응 허용&rsquo;을 켜면 MBON01이 발화하는 순간 몸이 실제로 회피합니다.
                  </p>
                )}
                <StatsPanel stats={state.stats} reachLabel={null} />
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
                    <strong>{lastTick?.event === "avoidance" ? "회피 중" : "순항 중"}</strong>
                    <span>현재 상태{manualTick ? " (뇌의 결정)" : ""}</span>
                  </div>
                </div>

                <LoopCharts
                  concentrationRows={chartRows.c}
                  neuronRows={chartRows.n}
                  neuronSeries={[{ name: "MBON01", color: CHART_COLORS[0] }]}
                  neuronTitle="MBON01(y5B'2a) 발화 수 (틱당)"
                  markLabel="뇌가 회피 결정"
                />

                {lastTick && (
                  <div className="disorder-group">
                    <small>가장 최근 틱의 실제 신경 활동{manualTick ? " (수동 조종 중)" : ""}</small>
                    <div className="worm-arena-controls" style={{ marginBottom: 6 }}>
                      <span className={`worm-event-badge ${lastTick.event}`}>{lastTick.event === "cruise" ? "cruise (순항)" : "avoidance (회피)"}</span>
                      <span className="panel-copy" style={{ margin: 0 }}>
                        PN(DA1) 자극전류 {lastTick.pn_current_na.toFixed(3)}nA · MBON01(y5B&apos;2a) {lastTick.mbon01_spikes}회 발화
                        {lastTick.z_um > 0 ? ` · 고도 ${(lastTick.z_um / 1000).toFixed(1)}mm` : ""}
                      </span>
                    </div>
                    <div className="worm-sensory-bars">
                      <div className="worm-sensory-bar-row">
                        <span>MBON01</span>
                        <span className="worm-sensory-bar-track">
                          <span className="worm-sensory-bar-fill" style={{ width: `${Math.min(100, (lastTick.mbon01_spikes / MBON_BAR_MAX) * 100)}%` }} />
                        </span>
                        <span>{lastTick.mbon01_spikes}</span>
                      </div>
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
                          {t.bio_time_s.toFixed(1)}s · C={t.concentration.toFixed(3)} · PN {t.pn_current_na.toFixed(3)}nA · MBON01 {t.mbon01_spikes}회
                          {t.z_um > 0 ? ` · 비행 ${(t.z_um / 1000).toFixed(1)}mm` : ""}
                          {t.control === "manual" ? " · 수동" : ""}
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
