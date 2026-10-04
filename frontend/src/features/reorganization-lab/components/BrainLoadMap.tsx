"use client";

import { useState } from "react";

import type { ReorgRegionState } from "@/types/lab";

/** 400개 영역을 MNI 좌표의 위에서 본 평면(x: 좌우, y: 앞뒤)에 찍고, 마지막 시기의 '정상 부하 대비 비율'을 발산형 색으로 칠한다
 * (docs/52). 발산형 = 파랑(정상보다 낮음) ↔ 회색(정상) ↔ 빨강(정상보다 높음), dataviz 기본 팔레트의 발산 쌍. 색만으로 상태를
 * 전하지 않도록 병변 영역은 ×, 마모로 잃은 영역은 빈 원으로 모양을 바꾼다. */

const LOW = [0x39, 0x87, 0xe5];
const MID = [0x38, 0x38, 0x35];
const HIGH = [0xe6, 0x67, 0x67];
const CLAMP = Math.log(3);

function mix(a: number[], b: number[], t: number): string {
  const c = a.map((v, i) => Math.round(v + (b[i] - v) * t));
  return `rgb(${c[0]},${c[1]},${c[2]})`;
}

export function ratioColor(r: number): string {
  const z = Math.max(-1, Math.min(1, Math.log(Math.max(r, 1e-3)) / CLAMP));
  return z < 0 ? mix(MID, LOW, -z) : mix(MID, HIGH, z);
}

const W = 260;
const H = 300;

export function BrainLoadMap({ title, regions, pick }: { title: string; regions: ReorgRegionState[]; pick: "none" | "closed" }) {
  const [hover, setHover] = useState<ReorgRegionState | null>(null);
  // MNI: x -70..70(좌우), y -105..70(뒤..앞) -- 앞쪽이 위로 오게
  const sx = (x: number) => 14 + ((x + 72) / 144) * (W - 28);
  const sy = (y: number) => 10 + ((72 - y) / 180) * (H - 20);
  const ratio = (r: ReorgRegionState) => (pick === "none" ? r.ratio_none : r.ratio_closed);
  const alive = (r: ReorgRegionState) => (pick === "none" ? r.alive_none : r.alive_closed);
  const nOver = regions.filter((r) => alive(r) && !r.lesioned && ratio(r) > 1.2).length;
  const nLost = regions.filter((r) => !r.lesioned && !alive(r)).length;

  return (
    <figure className="reorg-map">
      <figcaption>
        <strong>{title}</strong>
        <span>
          정상 부하 ×1.2 초과 {nOver}곳 · 마모로 잃음 {nLost}곳
        </span>
      </figcaption>
      <svg width={W} height={H} role="img" aria-label={`${title}: 영역별 정상 부하 대비 비율`}>
        <text x={W / 2} y={12} textAnchor="middle" className="vo-chart-tick">
          앞
        </text>
        <text x={6} y={H / 2} className="vo-chart-tick">
          좌
        </text>
        <text x={W - 6} y={H / 2} textAnchor="end" className="vo-chart-tick">
          우
        </text>
        {regions.map((r) => {
          const cx = sx(r.x);
          const cy = sy(r.y);
          const common = { onPointerEnter: () => setHover(r), onPointerLeave: () => setHover(null) };
          if (r.lesioned)
            return (
              <path key={r.id} d={`M${cx - 3},${cy - 3}L${cx + 3},${cy + 3}M${cx - 3},${cy + 3}L${cx + 3},${cy - 3}`} className="reorg-map-lesion" {...common} />
            );
          if (!alive(r)) return <circle key={r.id} cx={cx} cy={cy} r={3.5} className="reorg-map-lost" {...common} />;
          return <circle key={r.id} cx={cx} cy={cy} r={4} fill={ratioColor(ratio(r))} className="reorg-map-node" {...common} />;
        })}
      </svg>
      <div className="reorg-map-legend">
        <span>정상보다 낮음</span>
        <i style={{ background: `linear-gradient(90deg, ${ratioColor(1 / 3)}, ${ratioColor(1)}, ${ratioColor(3)})` }} />
        <span>높음(×3)</span>
        <em>× 병변 · ○ 마모로 잃음</em>
      </div>
      <p className="reorg-map-tip">
        {hover
          ? `영역 ${hover.id + 1} · ${hover.network} · ${
              hover.lesioned ? "병변" : !alive(hover) ? "마모로 잃음" : `정상 부하 대비 ×${ratio(hover).toFixed(2)}`
            }`
          : "점에 마우스를 올리면 영역 정보를 봅니다."}
      </p>
    </figure>
  );
}
