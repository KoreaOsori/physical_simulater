"use client";

import { useEffect, useRef, useState } from "react";

/** 시기(epoch)별 다중 계열 선 그래프(docs/52). 축 하나, 2px 선, 십자선+툴팁, 범례 + 계열 4개 이하일 때 끝점 직접 라벨.
 * 기준선(정상 뇌 등)은 계열 색이 아니라 회색 점선으로 그려 '비교 대상'임을 구분한다. 텍스트는 본문 색. */

export interface EpochSeries {
  key: string;
  name: string;
  color: string;
  values: number[];
  dashed?: boolean;
  /** 끝점 직접 라벨용 짧은 이름(없으면 name). */
  short?: string;
}

const H = 170;
const PAD = { l: 46, r: 14, t: 12, b: 24 };

function useWidth<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [w, setW] = useState(520);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setW(Math.max(240, Math.floor(e.contentRect.width))));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return { ref, w };
}

export function EpochLineChart({
  title,
  series,
  format,
  xLabel = "시기",
  yDomain,
}: {
  title: string;
  series: EpochSeries[];
  format: (v: number) => string;
  xLabel?: string;
  yDomain?: [number, number];
}) {
  const { ref, w } = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  const n = Math.max(0, ...series.map((s) => s.values.length));
  const all = series.flatMap((s) => s.values);
  let lo = yDomain ? yDomain[0] : Math.min(...all);
  let hi = yDomain ? yDomain[1] : Math.max(...all);
  if (!yDomain) {
    const pad = (hi - lo) * 0.08 || Math.abs(hi) * 0.05 || 1;
    lo -= pad;
    hi += pad;
  }
  const innerW = w - PAD.l - PAD.r;
  const innerH = H - PAD.t - PAD.b;
  const sx = (i: number) => PAD.l + (n <= 1 ? innerW : (i / (n - 1)) * innerW);
  const sy = (v: number) => PAD.t + innerH - ((v - lo) / (hi - lo || 1)) * innerH;
  const directLabels = series.filter((s) => !s.dashed).length <= 4;
  // 끝점 라벨이 겹치지 않게 위에서부터 최소 11px 간격으로 밀어낸다
  const labelY: Record<string, number> = {};
  if (directLabels) {
    const ends = series
      .filter((s) => !s.dashed && s.values.length)
      .map((s) => ({ key: s.key, y: sy(s.values[s.values.length - 1]) - 5 }))
      .sort((a, b) => a.y - b.y);
    let prev = -Infinity;
    for (const e of ends) {
      const y = Math.max(e.y, prev + 11);
      labelY[e.key] = y;
      prev = y;
    }
  }

  const onMove = (e: React.PointerEvent<SVGSVGElement>) => {
    if (n < 2) return;
    const px = e.clientX - e.currentTarget.getBoundingClientRect().left;
    setHover(Math.max(0, Math.min(n - 1, Math.round(((px - PAD.l) / innerW) * (n - 1)))));
  };

  return (
    <figure className="vo-chart" ref={ref}>
      <figcaption>
        <strong>{title}</strong>
        {series.length > 1 && (
          <span className="vo-chart-legend">
            {series.map((s) => (
              <span key={s.key}>
                <i style={s.dashed ? { background: "transparent", borderTop: `2px dashed ${s.color}`, height: 0 } : { background: s.color }} />
                {s.name}
              </span>
            ))}
          </span>
        )}
      </figcaption>
      {n < 2 ? (
        <p className="vo-chart-empty">시기가 두 개 이상이어야 그래프가 그려집니다.</p>
      ) : (
        <div className="vo-chart-plot">
          <svg width={w} height={H} onPointerMove={onMove} onPointerLeave={() => setHover(null)} role="img" aria-label={title}>
            {[0, 0.5, 1].map((f) => {
              const v = lo + (hi - lo) * f;
              return (
                <g key={f}>
                  <line x1={PAD.l} x2={w - PAD.r} y1={sy(v)} y2={sy(v)} className="vo-chart-grid" />
                  <text x={PAD.l - 6} y={sy(v) + 3} textAnchor="end" className="vo-chart-tick">
                    {format(v)}
                  </text>
                </g>
              );
            })}
            <text x={PAD.l} y={H - 6} className="vo-chart-tick">
              {xLabel} 0
            </text>
            <text x={w - PAD.r} y={H - 6} textAnchor="end" className="vo-chart-tick">
              {xLabel} {n - 1}
            </text>
            {series.map((s) => (
              <polyline
                key={s.key}
                fill="none"
                stroke={s.color}
                strokeWidth={2}
                strokeDasharray={s.dashed ? "5 4" : undefined}
                strokeLinejoin="round"
                strokeLinecap="round"
                points={s.values.map((v, i) => `${sx(i)},${sy(v)}`).join(" ")}
              />
            ))}
            {directLabels &&
              series
                .filter((s) => !s.dashed)
                .map((s) => (
                  <text key={`l${s.key}`} x={w - PAD.r} y={labelY[s.key]} textAnchor="end" className="vo-chart-direct">
                    {s.short ?? s.name}
                  </text>
                ))}
            {hover !== null && (
              <g>
                <line x1={sx(hover)} x2={sx(hover)} y1={PAD.t} y2={PAD.t + innerH} className="vo-chart-cross" />
                {series.map((s) =>
                  s.values[hover] === undefined ? null : <circle key={s.key} cx={sx(hover)} cy={sy(s.values[hover])} r={4} fill={s.color} className="vo-chart-dot" />,
                )}
              </g>
            )}
          </svg>
          {hover !== null && (
            <div className="vo-chart-tip" style={{ left: Math.min(w - 190, Math.max(0, sx(hover) + 8)) }}>
              <b>
                {xLabel} {hover}
              </b>
              {series.map((s) => (
                <div key={s.key}>
                  <i style={{ background: s.color }} />
                  {s.name}: {s.values[hover] === undefined ? "—" : format(s.values[hover])}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </figure>
  );
}
