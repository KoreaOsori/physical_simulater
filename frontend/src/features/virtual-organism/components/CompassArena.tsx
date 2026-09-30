"use client";

/** "나침반" 뷰 -- docs/41/42의 2D SVG 아레나(위에서 내려다본 지도 + 방향 화살표)를
 * 두 페이지가 공유하도록 뽑아낸 것. 수동 조향 중엔 키보드로 돌린 방향을 점선으로
 * 함께 그린다(docs/44). */

interface CompassArenaProps {
  idPrefix: string;
  arenaRadiusUm: number;
  sourceUm: [number, number];
  sigmaUm: number;
  trail: [number, number][];
  x_um: number;
  y_um: number;
  headingDeg: number;
  fieldColor: string;
  sourceColor: string;
  /** 수동 조종 중 시선(W 전진 방향) -- 점선으로 표시. */
  steerHeadingDeg: number | null;
  /** 냄새원 옮기기 모드일 때 아레나 클릭 -> 세계 좌표(μm). */
  onArenaClick: ((x_um: number, y_um: number) => void) | null;
}

function worldToScreen(x_um: number, y_um: number, radius_um: number): [number, number] {
  return [x_um / radius_um, -y_um / radius_um];
}

function trianglePoints(cx: number, cy: number, headingDeg: number, size: number): string {
  const rad = (headingDeg * Math.PI) / 180;
  const dirX = Math.cos(rad);
  const dirY = -Math.sin(rad); // 화면 y축이 world y축과 반대라서 부호 반전
  const tip: [number, number] = [cx + dirX * size, cy + dirY * size];
  const backAngle = (140 * Math.PI) / 180;
  const rot = (vx: number, vy: number, a: number): [number, number] => [vx * Math.cos(a) - vy * Math.sin(a), vx * Math.sin(a) + vy * Math.cos(a)];
  const [bx1, by1] = rot(dirX, dirY, backAngle);
  const [bx2, by2] = rot(dirX, dirY, -backAngle);
  return `${tip[0]},${tip[1]} ${cx + bx1 * size * 0.7},${cy + by1 * size * 0.7} ${cx + bx2 * size * 0.7},${cy + by2 * size * 0.7}`;
}

export function CompassArena({ idPrefix, arenaRadiusUm: R, sourceUm, sigmaUm, trail, x_um, y_um, headingDeg, fieldColor, sourceColor, steerHeadingDeg, onArenaClick }: CompassArenaProps) {
  const [sx, sy] = worldToScreen(sourceUm[0], sourceUm[1], R);
  const [ox, oy] = worldToScreen(x_um, y_um, R);
  const sigmaNorm = sigmaUm / R;
  const gradientStops = [0, 0.3, 0.6, 0.9, 1.2, 1.6, 2.2].map((rNorm) => {
    const rUm = rNorm * R;
    return { offset: Math.min(1, rNorm / 2.2), opacity: Math.exp(-(rUm * rUm) / (2 * sigmaUm * sigmaUm)) };
  });
  const trailPoints = trail.map(([x, y]) => worldToScreen(x, y, R).join(",")).join(" ");
  const gradId = `${idPrefix}-conc-gradient`;
  const steerRad = steerHeadingDeg === null ? 0 : (steerHeadingDeg * Math.PI) / 180;

  return (
    <svg
      viewBox="-1.15 -1.15 2.3 2.3"
      role="img"
      aria-label="위에서 내려다본 아레나 지도"
      style={{ cursor: onArenaClick ? "crosshair" : undefined }}
      onClick={
        onArenaClick
          ? (e) => {
              const svg = e.currentTarget;
              const pt = svg.createSVGPoint();
              pt.x = e.clientX;
              pt.y = e.clientY;
              const m = svg.getScreenCTM();
              if (!m) return;
              const p = pt.matrixTransform(m.inverse());
              onArenaClick(p.x * R, -p.y * R);
            }
          : undefined
      }
    >
      <defs>
        <radialGradient id={gradId} cx={(sx + 1) / 2} cy={(sy + 1) / 2} r={sigmaNorm * 1.1} gradientUnits="objectBoundingBox">
          {gradientStops.map((s, i) => (
            <stop key={i} offset={s.offset} stopColor={fieldColor} stopOpacity={s.opacity * 0.55} />
          ))}
        </radialGradient>
      </defs>
      <circle cx={0} cy={0} r={1} fill="#0c1410" stroke="#2a3a2c" strokeWidth={0.01} />
      <circle cx={0} cy={0} r={1} fill={`url(#${gradId})`} />
      {/* 나침반 방위 눈금 */}
      {[0, 90, 180, 270].map((deg) => {
        const r = (deg * Math.PI) / 180;
        return <line key={deg} x1={Math.cos(r) * 1.02} y1={-Math.sin(r) * 1.02} x2={Math.cos(r) * 1.08} y2={-Math.sin(r) * 1.08} stroke="#4a5a4c" strokeWidth={0.01} />;
      })}
      {trailPoints && <polyline points={trailPoints} fill="none" stroke="#4a6a4c" strokeWidth={0.006} opacity={0.8} />}
      <circle cx={sx} cy={sy} r={0.03} fill={sourceColor} stroke="#2a170b" strokeWidth={0.006} />
      <circle cx={sx} cy={sy} r={0.06} fill="none" stroke={sourceColor} strokeWidth={0.004} opacity={0.5} />
      {steerHeadingDeg !== null && (
        <line
          x1={ox}
          y1={oy}
          x2={ox + Math.cos(steerRad) * 0.16}
          y2={oy - Math.sin(steerRad) * 0.16}
          stroke="#7fdcff"
          strokeWidth={0.008}
          strokeDasharray="0.02 0.015"
        />
      )}
      <polygon points={trianglePoints(ox, oy, headingDeg, 0.035)} fill="#7fdc7f" />
    </svg>
  );
}
