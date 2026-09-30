"use client";

import { useCallback, useEffect, useRef, type MutableRefObject } from "react";

import type { OrganismKeys } from "@/features/virtual-organism/lib/use-organism-keys";
import type { VirtualOrganismPose, VirtualOrganismReflex } from "@/types/lab";

/** 수동 조종(docs/45) -- 개체를 브라우저에서 실시간으로, 실측 속도로 움직인다.
 *
 * docs/44에선 이동을 서버 틱 결과에 묶어 두었는데, 한 틱 계산에 실제로 수 초가
 * 걸려 W를 눌러도 몇 초 뒤에야, 그것도 웜은 30μm(체장의 3%)만 움직여 "앞으로 안
 * 간다"는 문제가 됐다. 이제 이동은 여기서 매 프레임 적분하고, 뇌 회로는 서버가
 * 이 위치를 계속 따라가며 계산한다(use-closed-loop.ts의 수동 감지 루프).
 *
 * 생물학적 시간 = 벽시계 시간 × 배속. 속도·회전율은 전부 생물학적 시간 기준. */

export interface PilotConfig {
  walkSpeedUmS: number;
  /** null이면 날 수 없다(웜). */
  flySpeedUmS: number | null;
  climbUmS: number;
  sinkUmS: number;
  walkTurnRadS: number;
  flyTurnRadS: number;
  arenaRadiusUm: number;
  ceilingUm: number;
  /** 궤적 점을 기록하는 최소 간격. */
  pathSpacingUm: number;
  /** 반사 동작(후진+재정향)을 보여주는 생물학적 시간. */
  reflexBioMs: number;
}

export interface PilotState {
  x_um: number;
  y_um: number;
  z_um: number;
  headingRad: number;
  /** 카메라가 바라보는 수평 방향(세계 좌표 heading, rad) -- W로 전진할 때 향하는 쪽. */
  viewYawRad: number;
  /** 3D 장면이 카메라로 viewYaw를 써 넣는 중이면 true(나침반 보기에선 방향키로 직접 돌린다). */
  cameraDriven: boolean;
  airborne: boolean;
  /** 이번 프레임에 실제로 움직였는가(걸음/날갯짓 표현용). */
  moving: boolean;
  turning: number;
  turnSign: number;
  reflex: { t: number; from: { x: number; y: number; h: number }; to: { x: number; y: number; h: number } } | null;
  // 서버 동기화용 누적값
  bioMsSinceSync: number;
  path: [number, number][];
  lastPathPoint: [number, number] | null;
  runId: number | undefined;
}

const VIEW_YAW_RATE = 1.6; // rad/s(벽시계) -- 나침반 보기에서 방향키로 시선을 돌리는 속도

function wrapPi(a: number): number {
  let d = a % (Math.PI * 2);
  if (d > Math.PI) d -= Math.PI * 2;
  if (d < -Math.PI) d += Math.PI * 2;
  return d;
}

function smooth(t: number): number {
  const c = Math.min(1, Math.max(0, t));
  return c * c * (3 - 2 * c);
}

export interface PilotHandle {
  pilotRef: MutableRefObject<PilotState>;
  /** 수동 조종을 시작할 때 서버의 현재 위치에서 출발. */
  init: (pose: { x_um: number; y_um: number; z_um?: number; heading_deg: number; run_id?: number }) => void;
  /** 서버로 보낼 현재 위치 + 직전 동기화 이후의 경로/생물학적 시간을 꺼낸다(누적값 초기화). */
  takeSync: () => VirtualOrganismPose;
  /** 뇌가 결정한 반사 동작을 "지금" 위치에서 실행한다. */
  playReflex: (reflex: VirtualOrganismReflex) => void;
}

export function usePilot(enabled: boolean, cfg: PilotConfig, keysRef: MutableRefObject<OrganismKeys>, timeScale: number): PilotHandle {
  const pilotRef = useRef<PilotState>({
    x_um: 0,
    y_um: 0,
    z_um: 0,
    headingRad: Math.PI / 2,
    viewYawRad: Math.PI / 2,
    cameraDriven: false,
    airborne: false,
    moving: false,
    turning: 0,
    turnSign: 1,
    reflex: null,
    bioMsSinceSync: 0,
    path: [],
    lastPathPoint: null,
    runId: undefined,
  });
  const cfgRef = useRef(cfg);
  const scaleRef = useRef(timeScale);
  useEffect(() => {
    cfgRef.current = cfg;
    scaleRef.current = timeScale;
  });

  const init = useCallback((pose: { x_um: number; y_um: number; z_um?: number; heading_deg: number; run_id?: number }) => {
    const p = pilotRef.current;
    p.runId = pose.run_id;
    p.x_um = pose.x_um;
    p.y_um = pose.y_um;
    p.z_um = pose.z_um ?? 0;
    p.airborne = p.z_um > 0;
    p.headingRad = (pose.heading_deg * Math.PI) / 180;
    if (!p.cameraDriven) p.viewYawRad = p.headingRad;
    p.reflex = null;
    p.turning = 0;
    p.bioMsSinceSync = 0;
    p.path = [];
    p.lastPathPoint = [p.x_um, p.y_um];
  }, []);

  const takeSync = useCallback((): VirtualOrganismPose => {
    const p = pilotRef.current;
    const pose: VirtualOrganismPose = {
      x_um: p.x_um,
      y_um: p.y_um,
      z_um: p.z_um,
      heading_deg: (((p.headingRad * 180) / Math.PI) % 360 + 360) % 360,
      elapsed_bio_ms: Math.min(120000, Math.max(1, p.bioMsSinceSync)),
      path: p.path.slice(-700),
      run_id: p.runId,
    };
    p.bioMsSinceSync = 0;
    p.path = [];
    return pose;
  }, []);

  const playReflex = useCallback((reflex: VirtualOrganismReflex) => {
    const p = pilotRef.current;
    const back = p.airborne ? 0 : reflex.back_um; // 공중에선 뒤로 걷지 않고 방향만 튼다(비행 중 회피 선회)
    const tx = p.x_um - back * Math.cos(p.headingRad);
    const ty = p.y_um - back * Math.sin(p.headingRad);
    p.reflex = {
      t: 0,
      from: { x: p.x_um, y: p.y_um, h: p.headingRad },
      to: { x: tx, y: ty, h: p.headingRad + wrapPi((reflex.new_heading_deg * Math.PI) / 180 - p.headingRad) },
    };
  }, []);

  useEffect(() => {
    if (!enabled) return;
    let raf = 0;
    let last = performance.now();
    const loop = (now: number) => {
      const wallDt = Math.min(0.1, (now - last) / 1000);
      last = now;
      const c = cfgRef.current;
      const bioDt = wallDt * scaleRef.current;
      const p = pilotRef.current;
      const k = keysRef.current;
      p.bioMsSinceSync += bioDt * 1000;

      if (!p.cameraDriven) p.viewYawRad = wrapPi(p.viewYawRad + ((k.left ? 1 : 0) - (k.right ? 1 : 0)) * VIEW_YAW_RATE * wallDt);

      let moved = false;
      if (p.reflex) {
        // 반사 동작: 전반부 후진, 후반부 제자리 재정향(자동 모드 보간과 같은 모양)
        p.reflex.t += (bioDt * 1000) / c.reflexBioMs;
        const t = p.reflex.t;
        const r = p.reflex;
        if (t < 0.5) {
          const u = smooth(t / 0.5);
          p.x_um = r.from.x + (r.to.x - r.from.x) * u;
          p.y_um = r.from.y + (r.to.y - r.from.y) * u;
          p.turning = 0;
        } else {
          const u = (t - 0.5) / 0.5;
          p.x_um = r.to.x;
          p.y_um = r.to.y;
          p.headingRad = r.from.h + (r.to.h - r.from.h) * smooth(u);
          p.turning = Math.sin(Math.PI * Math.min(1, u));
          p.turnSign = Math.sign(r.to.h - r.from.h) || 1;
        }
        moved = true;
        if (t >= 1) {
          p.reflex = null;
          p.turning = 0;
        }
      } else {
        p.turning = 0;
        // 비행(초파리)
        if (c.flySpeedUmS !== null) {
          if (k.fly) {
            p.airborne = true;
            p.z_um = Math.min(c.ceilingUm, p.z_um + c.climbUmS * bioDt);
          } else if (p.airborne) {
            p.z_um = Math.max(0, p.z_um - c.sinkUmS * bioDt);
            if (p.z_um <= 0) p.airborne = false;
          }
        }
        if (k.forward) {
          const turnRate = p.airborne ? c.flyTurnRadS : c.walkTurnRadS;
          const diff = wrapPi(p.viewYawRad - p.headingRad);
          const maxTurn = turnRate * bioDt;
          p.headingRad += Math.max(-maxTurn, Math.min(maxTurn, diff));
          const speed = p.airborne && c.flySpeedUmS !== null ? c.flySpeedUmS : c.walkSpeedUmS;
          p.x_um += Math.cos(p.headingRad) * speed * bioDt;
          p.y_um += Math.sin(p.headingRad) * speed * bioDt;
          moved = true;
        }
      }

      // 아레나 벽
      const r = Math.hypot(p.x_um, p.y_um);
      const limit = c.arenaRadiusUm * 0.985;
      if (r > limit) {
        p.x_um *= limit / r;
        p.y_um *= limit / r;
      }
      p.moving = moved;

      const lp = p.lastPathPoint;
      if (!lp || Math.hypot(p.x_um - lp[0], p.y_um - lp[1]) >= c.pathSpacingUm) {
        p.lastPathPoint = [p.x_um, p.y_um];
        p.path.push([p.x_um, p.y_um]);
      }
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [enabled, keysRef]);

  return { pilotRef, init, takeSync, playReflex };
}
