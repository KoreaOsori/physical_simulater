"use client";

import { useEffect, useRef, useState } from "react";

import type { VirtualOrganismStats } from "@/types/lab";

/** 폐루프 기록 그래프 + 통계(docs/45). 두 측정값(농도 0-1, 스파이크 수)은 단위가
 * 달라 한 축에 겹치지 않고 x축(생물학적 시간)을 공유하는 두 개의 작은 차트로 나눈다.
 * 색은 dataviz 기본 팔레트의 어두운 모드 1·2번(파랑/주황)을 이 페이지 배경(#07140f)에
 * 대해 검증한 값(CVD ΔE 26.8, 대비 3:1 이상). 텍스트는 시리즈 색이 아니라 본문 색. */

export interface ChartSeries {
  name: string;
  color: string;
}

export interface ChartRow {
  x: number;
  ys: number[];
  /** 뇌가 반전/회피를 결정한 틱이면 true -- 삼각형 표식(색 외의 2차 부호화). */
  marked?: boolean;
  manual?: boolean;
}

const SERIES_1 = "#3987e5";
const SERIES_2 = "#d95926";
export const CHART_COLORS = [SERIES_1, SERIES_2] as const;

const H = 120;
const PAD = { l: 34, r: 12, t: 10, b: 20 };

function useWidth<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [w, setW] = useState(480);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setW(Math.max(220, Math.floor(e.contentRect.width))));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return { ref, w };
}

function niceMax(v: number): number {
  if (v <= 1) return 1;
  const p = Math.pow(10, Math.floor(Math.log10(v)));
  for (const m of [1, 2, 5, 10]) if (m * p >= v) return m * p;
  return 10 * p;
}

function MiniLineChart({ title, rows, series, yMax, valueFormat, markLabel }: { title: string; rows: ChartRow[]; series: ChartSeries[]; yMax?: number; valueFormat: (v: number) => string; markLabel: string }) {
  const { ref, w } = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  const innerW = w - PAD.l - PAD.r;
  const innerH = H - PAD.t - PAD.b;
  const xs = rows.map((r) => r.x);
  const x0 = xs.length ? Math.min(...xs) : 0;
  const x1 = xs.length ? Math.max(...xs) : 1;
  const top = yMax ?? niceMax(Math.max(1, ...rows.flatMap((r) => r.ys)));
  const sx = (x: number) => PAD.l + (x1 === x0 ? innerW : ((x - x0) / (x1 - x0)) * innerW);
  const sy = (y: number) => PAD.t + innerH - (Math.min(y, top) / top) * innerH;

  const onMove = (e: React.PointerEvent<SVGSVGElement>) => {
    if (rows.length === 0) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const px = e.clientX - rect.left;
    let best = 0;
    let bestD = Infinity;
    rows.forEach((r, i) => {
      const d = Math.abs(sx(r.x) - px);
      if (d < bestD) {
        bestD = d;
        best = i;
      }
    });
    setHover(best);
  };

  const hovered = hover !== null ? rows[hover] : null;
  const last = rows[rows.length - 1];

  return (
    <figure className="vo-chart" ref={ref}>
      <figcaption>
        <strong>{title}</strong>
        {series.length > 1 && (
          <span className="vo-chart-legend">
            {series.map((s) => (
              <span key={s.name}>
                <i style={{ background: s.color }} />
                {s.name}
              </span>
            ))}
          </span>
        )}
      </figcaption>
      {rows.length < 2 ? (
        <p className="vo-chart-empty">틱이 두 개 이상 쌓이면 그래프가 그려집니다.</p>
      ) : (
        <div className="vo-chart-plot">
          <svg width={w} height={H} onPointerMove={onMove} onPointerLeave={() => setHover(null)} role="img" aria-label={title}>
            {[0, 0.5, 1].map((f) => (
              <g key={f}>
                <line x1={PAD.l} x2={w - PAD.r} y1={sy(top * f)} y2={sy(top * f)} className="vo-chart-grid" />
                <text x={PAD.l - 6} y={sy(top * f) + 3} textAnchor="end" className="vo-chart-tick">
                  {valueFormat(top * f)}
                </text>
              </g>
            ))}
            <text x={PAD.l} y={H - 5} className="vo-chart-tick">
              {x0.toFixed(1)}s
            </text>
            <text x={w - PAD.r} y={H - 5} textAnchor="end" className="vo-chart-tick">
              {x1.toFixed(1)}s (생물학적 시간)
            </text>
            {rows.map((r, i) =>
              r.marked ? (
                <path key={`m${i}`} d={`M${sx(r.x)},${PAD.t + 1} l-4,-0 l4,7 l4,-7 z`} className="vo-chart-mark">
                  <title>{markLabel}</title>
                </path>
              ) : null,
            )}
            {series.map((s, si) => (
              <polyline
                key={s.name}
                fill="none"
                stroke={s.color}
                strokeWidth={2}
                strokeLinejoin="round"
                strokeLinecap="round"
                points={rows.map((r) => `${sx(r.x)},${sy(r.ys[si] ?? 0)}`).join(" ")}
              />
            ))}
            {series.length > 1 &&
              last &&
              series.map((s, si) => (
                <text key={`lbl${s.name}`} x={w - PAD.r} y={sy(last.ys[si] ?? 0) - 5} textAnchor="end" className="vo-chart-direct">
                  {s.name}
                </text>
              ))}
            {hovered && (
              <g>
                <line x1={sx(hovered.x)} x2={sx(hovered.x)} y1={PAD.t} y2={PAD.t + innerH} className="vo-chart-cross" />
                {series.map((s, si) => (
                  <circle key={s.name} cx={sx(hovered.x)} cy={sy(hovered.ys[si] ?? 0)} r={4} fill={s.color} className="vo-chart-dot" />
                ))}
              </g>
            )}
          </svg>
          {hovered && (
            <div className="vo-chart-tip" style={{ left: Math.min(w - 150, Math.max(0, sx(hovered.x) + 8)) }}>
              <b>{hovered.x.toFixed(2)}s</b>
              {hovered.manual ? " · 수동" : " · 자동"}
              {series.map((s, si) => (
                <div key={s.name}>
                  <i style={{ background: s.color }} />
                  {s.name}: {valueFormat(hovered.ys[si] ?? 0)}
                </div>
              ))}
              {hovered.marked && <div>▼ {markLabel}</div>}
            </div>
          )}
        </div>
      )}
    </figure>
  );
}

export function LoopCharts({
  concentrationRows,
  neuronRows,
  neuronSeries,
  neuronTitle,
  markLabel,
}: {
  concentrationRows: ChartRow[];
  neuronRows: ChartRow[];
  neuronSeries: ChartSeries[];
  neuronTitle: string;
  markLabel: string;
}) {
  return (
    <div className="vo-charts">
      <MiniLineChart
        title="현재 위치 농도 (0–1)"
        rows={concentrationRows}
        series={[{ name: "농도", color: SERIES_1 }]}
        yMax={1}
        valueFormat={(v) => v.toFixed(2)}
        markLabel={markLabel}
      />
      <MiniLineChart title={neuronTitle} rows={neuronRows} series={neuronSeries} valueFormat={(v) => String(Math.round(v))} markLabel={markLabel} />
    </div>
  );
}

export function StatsPanel({ stats, reachLabel }: { stats: VirtualOrganismStats; reachLabel: string | null }) {
  return (
    <div className="vo-stats">
      <div className="lab-metric">
        <strong>{stats.bio_time_s.toFixed(1)}s</strong>
        <span>생물학적 시간</span>
      </div>
      <div className="lab-metric">
        <strong>{stats.distance_mm.toFixed(stats.distance_mm < 10 ? 2 : 1)}mm</strong>
        <span>이동 거리</span>
      </div>
      <div className="lab-metric">
        <strong>{stats.closest_approach_mm.toFixed(1)}mm</strong>
        <span>광원 최근접 거리</span>
      </div>
      <div className="lab-metric">
        <strong>{stats.reorient_decisions}</strong>
        <span>뇌의 반전/회피 결정</span>
        <em>
          자동 {stats.auto_ticks}틱 · 수동 {stats.manual_ticks}틱
        </em>
      </div>
      {reachLabel !== null && (
        <div className="lab-metric">
          <strong>{stats.reached_at_s === null ? "—" : `${stats.reached_at_s.toFixed(1)}s`}</strong>
          <span>{reachLabel}</span>
        </div>
      )}
    </div>
  );
}
