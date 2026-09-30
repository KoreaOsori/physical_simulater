"use client";

import { useEffect, useState, type MutableRefObject } from "react";

import { CompassArena } from "@/features/virtual-organism/components/CompassArena";
import type { CameraMode } from "@/features/virtual-organism/components/OrganismDriver";
import { SceneErrorBoundary } from "@/features/virtual-organism/components/SceneErrorBoundary";
import { VirtualLabScene, type Species } from "@/features/virtual-organism/components/VirtualLabScene";
import type { MotionPlan } from "@/features/virtual-organism/lib/motion";
import type { OrganismKeys } from "@/features/virtual-organism/lib/use-organism-keys";
import type { PilotState } from "@/features/virtual-organism/lib/use-pilot";

export type StageView = "compass" | "lab3d";
export type ControlMode = "auto" | "manual";

interface StageState {
  x_um: number;
  y_um: number;
  z_um?: number;
  heading_deg: number;
  arena_radius_um: number;
  chamber_height_um?: number;
  source_x_um: number;
  source_y_um: number;
  gradient_sigma_um: number;
  trail: [number, number][];
}

interface OrganismStageProps {
  species: Species;
  state: StageState;
  motion: MotionPlan;
  mode: ControlMode;
  onModeChange: (m: ControlMode) => void;
  keysRef: MutableRefObject<OrganismKeys>;
  pressed: OrganismKeys;
  pilotRef: MutableRefObject<PilotState>;
  /** 좌상단 상태 칩 -- 이번 틱 행동. */
  statusLabel: string;
  statusTone: "calm" | "alert";
  /** 수동 모드에서 "뇌는 이렇게 결정했다"를 보여주는 한 줄. */
  brainNote: string | null;
  fieldColor: string;
  sourceColor: string;
  lastStepMs: number | null;
  reconnecting: boolean;
  timeScale: number;
  timeScaleOptions: number[];
  onTimeScale: (s: number) => void;
  allowReflex: boolean;
  onAllowReflex: (v: boolean) => void;
  onPlaceSource: (x_um: number, y_um: number) => void;
}

const VIEW_STORAGE_KEY = "virtual-organism-view";

function readStoredView(): StageView {
  try {
    const v = window.localStorage.getItem(VIEW_STORAGE_KEY);
    return v === "compass" || v === "lab3d" ? v : "lab3d";
  } catch {
    return "lab3d";
  }
}

interface LivePose {
  x_um: number;
  y_um: number;
  z_um: number;
  heading_deg: number;
  view_deg: number;
  airborne: boolean;
}

const toDeg = (rad: number) => (((rad * 180) / Math.PI) % 360 + 360) % 360;

/** 나침반(2D 지도) / 3D 실험실 두 보기를 전환하는 무대(docs/44, docs/45 확장). 두 보기는
 * 같은 상태의 다른 표현이다. 수동 조종 중엔 서버 응답(수 초 간격)이 아니라 브라우저가
 * 실시간으로 움직이는 조종 상태를 그린다. */
export function OrganismStage(props: OrganismStageProps) {
  const {
    species,
    state,
    motion,
    mode,
    onModeChange,
    keysRef,
    pressed,
    pilotRef,
    statusLabel,
    statusTone,
    brainNote,
    fieldColor,
    sourceColor,
    lastStepMs,
    reconnecting,
    timeScale,
    timeScaleOptions,
    onTimeScale,
    allowReflex,
    onAllowReflex,
    onPlaceSource,
  } = props;
  const [view, setView] = useState<StageView>("lab3d");
  const [cameraMode, setCameraMode] = useState<CameraMode>("follow");
  const [showField, setShowField] = useState(true);
  const [placing, setPlacing] = useState(false);
  const [live, setLive] = useState<LivePose | null>(null);
  const manual = mode === "manual";

  // 마지막으로 고른 보기를 기억(뷰어별 편의 설정일 뿐 -- 없거나 실패해도 3D가 기본)
  useEffect(() => {
    const stored = readStoredView();
    if (stored !== "lab3d") setView(stored); // eslint-disable-line react-hooks/set-state-in-effect
  }, []);
  const chooseView = (v: StageView) => {
    setView(v);
    try {
      window.localStorage.setItem(VIEW_STORAGE_KEY, v);
    } catch {
      /* 저장 불가 환경이면 무시 */
    }
  };

  // 수동 조종 중 조종 상태를 10Hz로 읽어 나침반·HUD에 반영
  useEffect(() => {
    if (!manual) return;
    const id = window.setInterval(() => {
      const p = pilotRef.current;
      setLive({ x_um: p.x_um, y_um: p.y_um, z_um: p.z_um, heading_deg: toDeg(p.headingRad), view_deg: toDeg(p.viewYawRad), airborne: p.airborne });
    }, 100);
    return () => window.clearInterval(id);
  }, [manual, pilotRef]);

  const pose = manual && live ? live : { x_um: state.x_um, y_um: state.y_um, z_um: state.z_um ?? 0, heading_deg: state.heading_deg, view_deg: state.heading_deg, airborne: false };
  const sourceBearing = (Math.atan2(state.source_y_um - pose.y_um, state.source_x_um - pose.x_um) * 180) / Math.PI;
  const canFly = species === "fly";

  const place = placing
    ? (x_um: number, y_um: number) => {
        setPlacing(false);
        onPlaceSource(x_um, y_um);
      }
    : null;

  return (
    <div className="vo-stage-block">
      <div className="vo-toolbar" role="toolbar" aria-label="보기 및 조작 방식">
        <div className="vo-segmented" role="group" aria-label="보기">
          <button type="button" aria-pressed={view === "compass"} onClick={() => chooseView("compass")}>
            나침반
          </button>
          <button type="button" aria-pressed={view === "lab3d"} onClick={() => chooseView("lab3d")}>
            3D 실험실
          </button>
        </div>
        <div className="vo-segmented" role="group" aria-label="조작 방식">
          <button type="button" aria-pressed={!manual} onClick={() => onModeChange("auto")}>
            자동(커넥톰)
          </button>
          <button type="button" aria-pressed={manual} onClick={() => onModeChange("manual")}>
            수동 조종
          </button>
        </div>
        {view === "lab3d" && (
          <>
            <div className="vo-segmented" role="group" aria-label="카메라">
              <button type="button" aria-pressed={cameraMode === "follow"} onClick={() => setCameraMode("follow")}>
                추적 카메라
              </button>
              <button type="button" aria-pressed={cameraMode === "overview"} onClick={() => setCameraMode("overview")}>
                전체 보기
              </button>
            </div>
            <button type="button" className="vo-toggle" aria-pressed={showField} onClick={() => setShowField((v) => !v)}>
              농도장 표시
            </button>
          </>
        )}
        <button type="button" className="vo-toggle" aria-pressed={placing} onClick={() => setPlacing((v) => !v)}>
          {placing ? "냄새원 옮기기 취소" : "냄새원 옮기기"}
        </button>
      </div>

      {manual && (
        <div className="vo-toolbar vo-toolbar-sub" role="group" aria-label="수동 조종 설정">
          <span className="vo-toolbar-label">배속(생물학적 시간)</span>
          <div className="vo-segmented" role="group" aria-label="배속">
            {timeScaleOptions.map((s) => (
              <button key={s} type="button" aria-pressed={timeScale === s} onClick={() => onTimeScale(s)}>
                {s}×
              </button>
            ))}
          </div>
          <button type="button" className="vo-toggle" aria-pressed={allowReflex} onClick={() => onAllowReflex(!allowReflex)}>
            반사 반응 허용(공동 조종)
          </button>
        </div>
      )}

      <div className={`vo-stage ${view}`}>
        {view === "compass" ? (
          <div className="vo-compass-wrap">
            <CompassArena
              idPrefix={species}
              arenaRadiusUm={state.arena_radius_um}
              sourceUm={[state.source_x_um, state.source_y_um]}
              sigmaUm={state.gradient_sigma_um}
              trail={state.trail}
              x_um={pose.x_um}
              y_um={pose.y_um}
              headingDeg={pose.heading_deg}
              fieldColor={fieldColor}
              sourceColor={sourceColor}
              steerHeadingDeg={manual ? pose.view_deg : null}
              onArenaClick={place}
            />
          </div>
        ) : (
          <SceneErrorBoundary
            fallback={<p className="vo-stage-fallback">이 브라우저에서 3D(WebGL)를 표시하지 못했습니다 — 위에서 &lsquo;나침반&rsquo; 보기로 전환해주세요.</p>}
          >
            <VirtualLabScene
              species={species}
              arenaRadiusUm={state.arena_radius_um}
              sourceUm={[state.source_x_um, state.source_y_um]}
              sigmaUm={state.gradient_sigma_um}
              trail={state.trail}
              motion={motion}
              pilotRef={manual ? pilotRef : null}
              keysRef={keysRef}
              showField={showField}
              cameraMode={cameraMode}
              chamberHeightMm={(state.chamber_height_um ?? 0) / 1000}
              onFloorClick={place}
            />
          </SceneErrorBoundary>
        )}

        <div className="vo-hud vo-hud-status">
          <span className={`vo-chip ${statusTone}`}>{statusLabel}</span>
          <span className={`vo-chip ${manual ? "manual" : "auto"}`}>{manual ? "수동 조종" : "자동 · 커넥톰 결정"}</span>
          {canFly && manual && pose.airborne && <span className="vo-chip manual">비행 중 · 고도 {(pose.z_um / 1000).toFixed(1)}mm</span>}
          {reconnecting && <span className="vo-chip alert">백엔드 재연결 중…</span>}
          {brainNote && <span className="vo-brain-note">{brainNote}</span>}
        </div>

        {placing && <div className="vo-hud vo-hud-place">바닥(아레나 안)을 클릭하면 냄새원이 그 자리로 옮겨집니다</div>}

        <div className="vo-hud vo-hud-compass" aria-hidden>
          {view === "lab3d" && (
            <>
              <svg viewBox="-1 -1 2 2">
                <circle r={0.92} fill="rgba(10,14,12,0.72)" stroke="#3b4a3e" strokeWidth={0.05} />
                {["E", "N", "W", "S"].map((l, i) => {
                  const a = (i * Math.PI) / 2;
                  return (
                    <text key={l} x={Math.cos(a) * 0.7} y={-Math.sin(a) * 0.7 + 0.08} fontSize={0.24} textAnchor="middle" fill="#7d8d80">
                      {l}
                    </text>
                  );
                })}
                <line
                  x1={0}
                  y1={0}
                  x2={Math.cos((sourceBearing * Math.PI) / 180) * 0.55}
                  y2={-Math.sin((sourceBearing * Math.PI) / 180) * 0.55}
                  stroke={sourceColor}
                  strokeWidth={0.07}
                  strokeLinecap="round"
                  opacity={0.8}
                />
                <polygon points="0.62,0 -0.3,0.24 -0.16,0 -0.3,-0.24" fill={manual ? "#7fdcff" : "#7fdc7f"} transform={`rotate(${-pose.heading_deg})`} />
              </svg>
              <small>진행 {pose.heading_deg.toFixed(0)}°</small>
            </>
          )}
        </div>

        <div className="vo-hud vo-hud-keys">
          <kbd className={pressed.left ? "on" : ""}>←</kbd>
          <kbd className={pressed.right ? "on" : ""}>→</kbd>
          <kbd className={pressed.up ? "on" : ""}>↑</kbd>
          <kbd className={pressed.down ? "on" : ""}>↓</kbd> 시선
          {manual ? (
            <>
              {" · "}
              <kbd className={pressed.forward ? "on" : ""}>W</kbd> 시선 방향으로 전진
              {canFly && (
                <>
                  {" · "}
                  <kbd className={`wide ${pressed.fly ? "on" : ""}`}>Space</kbd> 날기(누르는 동안 상승)
                </>
              )}
            </>
          ) : (
            <span className="vo-forward"> · 직접 움직이려면 &lsquo;수동 조종&rsquo;</span>
          )}
        </div>

        <div className="vo-hud vo-hud-note">
          {view === "lab3d" ? "드래그 회전 · 휠 확대 · 실제 크기 비율(자 눈금 = cm)" : "위에서 본 지도"}
          {lastStepMs !== null && <> · 뇌 계산 {(lastStepMs / 1000).toFixed(1)}s/회</>}
          {manual ? <> · 이동은 실시간 × {timeScale}</> : <> · 자동은 계산 속도로 느리게 재생</>}
        </div>
      </div>
    </div>
  );
}
