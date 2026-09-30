/** 틱 사이 보간(docs/44). 백엔드 폐루프는 틱(생물학적 100ms)마다 위치/방향을
 * 한 번씩만 돌려주고, 한 틱 계산에 실제로 수백 ms~수 초가 걸린다. 3D 장면이
 * 순간이동하지 않게, 방금 받은 틱들을 "그 요청에 실제로 걸린 벽시계 시간"
 * 동안 순서대로 재생한다 -- 자동 재생 중엔 다음 응답이 대략 그만큼 뒤에
 * 오므로 끊김 없이 이어진다. 보간은 화면 표현일 뿐, 궤적 자체(각 틱의 끝
 * 위치/방향)는 전부 백엔드가 계산한 값 그대로다. */

export interface Pose {
  x_um: number;
  y_um: number;
  heading_deg: number;
}

export interface MotionSegment {
  from: Pose;
  to: Pose;
  /** true면 "후진 -> 제자리 재정향" 2단계(웜 pirouette / 초파리 avoidance),
   * false면 이동과 방향 변화를 동시에 보간(run / cruise / 수동 조향). */
  reorient: boolean;
}

export interface MotionPlan {
  segments: MotionSegment[];
  startedAt: number;
  durationMs: number;
}

export interface SampledPose {
  x_um: number;
  y_um: number;
  headingRad: number;
  /** 0-1, 제자리 재정향 구간에서 몸을 크게 굽히는 정도(웜 오메가 굽힘 표현용). */
  turning: number;
  /** 재정향 방향(+1 반시계 / -1 시계). */
  turnSign: number;
}

export function staticPlan(pose: Pose): MotionPlan {
  return { segments: [{ from: pose, to: pose, reorient: false }], startedAt: 0, durationMs: 1 };
}

function shortestDeltaRad(fromRad: number, toRad: number): number {
  let d = (toRad - fromRad) % (Math.PI * 2);
  if (d > Math.PI) d -= Math.PI * 2;
  if (d < -Math.PI) d += Math.PI * 2;
  return d;
}

function smoothstep(t: number): number {
  const c = Math.min(1, Math.max(0, t));
  return c * c * (3 - 2 * c);
}

const REORIENT_BACK_FRACTION = 0.5;

export function samplePlan(plan: MotionPlan, now: number): SampledPose {
  const n = plan.segments.length;
  const progress = Math.min(1, Math.max(0, (now - plan.startedAt) / plan.durationMs)) * n;
  const index = Math.min(n - 1, Math.floor(progress));
  const p = progress >= n ? 1 : progress - index;
  const seg = plan.segments[index];

  const fromRad = (seg.from.heading_deg * Math.PI) / 180;
  const dHeading = shortestDeltaRad(fromRad, (seg.to.heading_deg * Math.PI) / 180);

  if (seg.reorient) {
    if (p < REORIENT_BACK_FRACTION) {
      const t = smoothstep(p / REORIENT_BACK_FRACTION);
      return {
        x_um: seg.from.x_um + (seg.to.x_um - seg.from.x_um) * t,
        y_um: seg.from.y_um + (seg.to.y_um - seg.from.y_um) * t,
        headingRad: fromRad,
        turning: 0,
        turnSign: Math.sign(dHeading) || 1,
      };
    }
    const t = (p - REORIENT_BACK_FRACTION) / (1 - REORIENT_BACK_FRACTION);
    return {
      x_um: seg.to.x_um,
      y_um: seg.to.y_um,
      headingRad: fromRad + dHeading * smoothstep(t),
      turning: Math.sin(Math.PI * t),
      turnSign: Math.sign(dHeading) || 1,
    };
  }

  return {
    x_um: seg.from.x_um + (seg.to.x_um - seg.from.x_um) * p,
    y_um: seg.from.y_um + (seg.to.y_um - seg.from.y_um) * p,
    headingRad: fromRad + dHeading * smoothstep(p),
    turning: 0,
    turnSign: 1,
  };
}

/** 세계 좌표(μm, 수학 좌표계 x/y) -> 장면 좌표(mm). 장면은 y-up이라 세계 +y를
 * 장면 -z(카메라에서 멀어지는 쪽)로 둔다. 모델은 +x를 앞으로 만들어 두고
 * rotation.y = heading(rad)만 주면 (cos, 0, -sin) 방향을 향하게 된다. */
export function worldToSceneMm(x_um: number, y_um: number): [number, number] {
  return [x_um / 1000, -y_um / 1000];
}
