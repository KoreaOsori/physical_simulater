"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { staticPlan, type MotionPlan, type MotionSegment, type Pose } from "@/features/virtual-organism/lib/motion";
import type { PilotHandle } from "@/features/virtual-organism/lib/use-pilot";
import { ApiError } from "@/shared/lib/api-client";
import type { VirtualOrganismControl, VirtualOrganismPose, VirtualOrganismReflex } from "@/types/lab";

/** 웜/초파리 폐루프 페이지가 공유하는 상태 머신(docs/44에서 추출, docs/45에서 확장).
 *
 * - 자동: 서버 틱을 요청하고, 받은 틱들을 걸린 벽시계 시간 동안 보간 재생.
 * - 수동: 개체는 use-pilot.ts가 실시간으로 움직이고, 여기선 그 위치를 계속 서버로
 *   보내 실제 회로가 감각을 계산하게 한다(요청 하나 끝나면 바로 다음 요청).
 *
 * 동시성 규칙은 docs/43 그대로(자동 재생 중 다시 시작/배치 버튼 비활성). 다시 시작
 * 도중 날아가던 응답은 epoch로 걸러 옛 상태가 새 상태를 덮지 않게 한다. */

interface LoopState {
  tick: number;
  x_um: number;
  y_um: number;
  heading_deg: number;
}

interface LoopTick extends LoopState {
  event: string;
  control: VirtualOrganismControl;
  reflex: VirtualOrganismReflex | null;
  bio_time_s: number;
}

export interface ClosedLoopApi<S extends LoopState, T extends LoopTick> {
  fetchState: () => Promise<S>;
  reset: () => Promise<S>;
  step: (nTicks: number, manual: VirtualOrganismPose | null) => Promise<{ ticks: T[]; state: S }>;
  setSource: (x_um: number, y_um: number) => Promise<S>;
  setPose: (pose: VirtualOrganismPose) => Promise<S>;
  /** 이 이벤트면 "후진 -> 재정향" 2단계로 보간(웜 pirouette, 초파리 avoidance). */
  reorientEvent: string;
  label: string;
}

const MAX_LOGGED_TICKS = 60;
const MAX_HISTORY = 240;
const MIN_ANIM_MS = 350;
const MAX_ANIM_MS = 12000;
const RETRY_DELAYS_MS = [800, 2000, 4000];

function poseOf(s: LoopState): Pose {
  return { x_um: s.x_um, y_um: s.y_um, heading_deg: s.heading_deg };
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/** "Failed to fetch"(TypeError -- 연결이 끊김/재시작 중)만 재시도한다. 서버가 응답한
 * 오류(4xx/5xx)는 재시도해도 같은 결과라 바로 올린다. 틱 요청은 멱등이 아니라서, 연결이
 * 요청 처리 뒤에 끊긴 드문 경우엔 틱이 한 번 더 진행될 수 있다 -- 멈추는 것보다 낫다고 판단. */
async function withRetry<R>(fn: () => Promise<R>, isCancelled: () => boolean): Promise<R> {
  for (let attempt = 0; ; attempt++) {
    try {
      return await fn();
    } catch (err) {
      if (!(err instanceof TypeError) || attempt >= RETRY_DELAYS_MS.length || isCancelled()) throw err;
      await sleep(RETRY_DELAYS_MS[attempt]);
    }
  }
}

export interface ClosedLoopOptions {
  manual: boolean;
  pilot: PilotHandle;
  /** 수동 조종 중 뇌가 반전/회피를 결정하면 그 반사를 실제로 실행할지. */
  allowReflex: boolean;
}

export function useClosedLoop<S extends LoopState, T extends LoopTick>(api: ClosedLoopApi<S, T>, opts: ClosedLoopOptions) {
  const [state, setState] = useState<S | null>(null);
  const [recentTicks, setRecentTicks] = useState<T[]>([]);
  const [history, setHistory] = useState<T[]>([]);
  const [loading, setLoading] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [motion, setMotion] = useState<MotionPlan | null>(null);
  const [lastStepMs, setLastStepMs] = useState<number | null>(null);
  const [reconnecting, setReconnecting] = useState(false);

  const apiRef = useRef(api);
  const optsRef = useRef(opts);
  const stateRef = useRef<S | null>(null);
  const epochRef = useRef(0);
  useEffect(() => {
    apiRef.current = api;
    optsRef.current = opts;
  });

  const applyFresh = useCallback((s: S) => {
    stateRef.current = s;
    setState(s);
    setMotion(staticPlan(poseOf(s)));
  }, []);

  const pushTicks = useCallback((ticks: T[]) => {
    const newestFirst = [...ticks].reverse();
    setRecentTicks((prev) => [...newestFirst, ...prev].slice(0, MAX_LOGGED_TICKS));
    setHistory((prev) => [...prev, ...ticks].slice(-MAX_HISTORY));
  }, []);

  useEffect(() => {
    apiRef.current
      .fetchState()
      .then(applyFresh)
      .catch((err: unknown) => {
        console.warn(`Failed to load ${apiRef.current.label} state`, err);
        setError("환경을 불러오지 못했습니다 — 백엔드가 켜져 있는지 확인하고 페이지를 새로고침해보세요.");
      });
  }, [applyFresh]);

  const guarded = useCallback(<R,>(fn: () => Promise<R>, epoch: number) => {
    return withRetry(
      async () => {
        try {
          const r = await fn();
          setReconnecting(false);
          return r;
        } catch (err) {
          if (err instanceof TypeError) setReconnecting(true);
          throw err;
        }
      },
      () => epoch !== epochRef.current,
    );
  }, []);

  /** 자동 틱 요청 1회 -- 받은 틱들을 걸린 벽시계 시간 동안 순서대로 재생하도록 모션 계획을 만든다. */
  const runAutoStep = useCallback(
    async (n: number) => {
      const epoch = epochRef.current;
      const started = performance.now();
      const resp = await guarded(() => apiRef.current.step(n, null), epoch);
      if (epoch !== epochRef.current) return;
      const elapsed = performance.now() - started;

      let from = stateRef.current ? poseOf(stateRef.current) : poseOf(resp.state);
      const segments: MotionSegment[] = resp.ticks.map((t) => {
        const to = poseOf(t);
        const seg = { from, to, reorient: t.control === "auto" && t.event === apiRef.current.reorientEvent };
        from = to;
        return seg;
      });
      if (segments.length === 0) segments.push({ from, to: poseOf(resp.state), reorient: false });

      stateRef.current = resp.state;
      setState(resp.state);
      pushTicks(resp.ticks);
      setLastStepMs(elapsed);
      setMotion({ segments, startedAt: performance.now(), durationMs: Math.min(MAX_ANIM_MS, Math.max(MIN_ANIM_MS, elapsed * 0.95)) });
    },
    [guarded, pushTicks],
  );

  // 자동 재생 루프
  const playingRef = useRef(false);
  useEffect(() => {
    playingRef.current = playing;
    if (!playing) return;
    let cancelled = false;
    const loop = async () => {
      while (!cancelled && playingRef.current) {
        try {
          await runAutoStep(1);
        } catch (err: unknown) {
          console.warn(`Auto-step failed for ${apiRef.current.label}`, err);
          setError("시뮬레이션 진행 중 오류가 발생했습니다(재시도 후에도 실패) — 자동 재생을 멈췄습니다.");
          setPlaying(false);
          return;
        }
      }
    };
    void loop();
    return () => {
      cancelled = true;
    };
  }, [playing, runAutoStep]);

  // 수동 감지 루프 -- 요청 하나가 끝나면 바로 다음 요청(뇌 계산 속도가 곧 감지 주기)
  const { manual } = opts;
  useEffect(() => {
    if (!manual) return;
    let cancelled = false;
    const loop = async () => {
      // 조종 시작 직후 첫 경로가 쌓일 시간을 약간 둔다
      await sleep(250);
      while (!cancelled) {
        const epoch = epochRef.current;
        const pose = optsRef.current.pilot.takeSync();
        const started = performance.now();
        try {
          const resp = await guarded(() => apiRef.current.step(1, pose), epoch);
          if (cancelled || epoch !== epochRef.current) continue;
          stateRef.current = resp.state;
          setState(resp.state);
          pushTicks(resp.ticks);
          setLastStepMs(performance.now() - started);
          const reflex = resp.ticks[0]?.reflex;
          if (reflex && optsRef.current.allowReflex) optsRef.current.pilot.playReflex(reflex);
        } catch (err: unknown) {
          if (cancelled) return;
          if (err instanceof ApiError && err.status === 409) {
            // 다시 시작 직전에 보낸 옛 기록의 위치 -- 서버가 거절했으니 현재 기록으로 다시 맞춘다
            try {
              const s = await apiRef.current.fetchState();
              if (cancelled) return;
              applyFresh(s);
              optsRef.current.pilot.init(s);
            } catch {
              /* 다음 반복에서 다시 시도 */
            }
            continue;
          }
          console.warn(`Manual sensing failed for ${apiRef.current.label}`, err);
          setError("뇌 계산 요청이 실패했습니다(재시도 후에도 실패) — 잠시 후 다시 시도합니다.");
          await sleep(5000);
          setError(null);
        }
      }
    };
    void loop();
    return () => {
      cancelled = true;
    };
  }, [manual, guarded, pushTicks, applyFresh]);

  const reset = async () => {
    epochRef.current += 1;
    setPlaying(false);
    setLoading(true);
    setError(null);
    try {
      const s = await guarded(() => apiRef.current.reset(), epochRef.current);
      applyFresh(s);
      setRecentTicks([]);
      setHistory([]);
      optsRef.current.pilot.init(s);
    } catch (err: unknown) {
      console.warn(`Failed to reset ${api.label}`, err);
      setError("초기화하지 못했습니다 — 잠시 후 다시 시도해주세요.");
    } finally {
      setLoading(false);
    }
  };

  const stepBatch = async (n: number) => {
    setLoading(true);
    setError(null);
    try {
      await runAutoStep(n);
    } catch (err: unknown) {
      console.warn(`Failed to step ${api.label}`, err);
      setError("시뮬레이션을 진행하지 못했습니다 — 잠시 후 다시 시도해주세요.");
    } finally {
      setLoading(false);
    }
  };

  const moveSource = async (x_um: number, y_um: number) => {
    setError(null);
    try {
      const s = await guarded(() => apiRef.current.setSource(x_um, y_um), epochRef.current);
      stateRef.current = s;
      setState(s);
      setHistory([]);
      if (!optsRef.current.manual) setMotion(staticPlan(poseOf(s)));
    } catch (err: unknown) {
      console.warn(`Failed to move ${api.label} source`, err);
      setError("냄새원을 옮기지 못했습니다 — 잠시 후 다시 시도해주세요.");
    }
  };

  /** 수동 -> 자동: 브라우저에서 움직인 마지막 위치를 서버 상태로 확정한 뒤 자동으로. */
  const commitPose = async (pose: VirtualOrganismPose) => {
    epochRef.current += 1; // 날아가던 수동 감지 응답이 확정 위치를 되돌리지 않게
    try {
      const s = await guarded(() => apiRef.current.setPose(pose), epochRef.current);
      applyFresh(s);
    } catch (err: unknown) {
      console.warn(`Failed to commit ${api.label} pose`, err);
      setError("현재 위치를 서버에 반영하지 못했습니다 — 자동 모드는 마지막으로 계산된 위치에서 이어집니다.");
    }
  };

  return {
    state,
    recentTicks,
    history,
    loading,
    playing,
    setPlaying,
    error,
    motion,
    lastStepMs,
    reconnecting,
    reset,
    stepBatch,
    moveSource,
    commitPose,
  };
}
