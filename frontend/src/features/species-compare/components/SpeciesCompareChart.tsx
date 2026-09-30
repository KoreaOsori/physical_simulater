"use client";

import { useState } from "react";

export interface CompareBar {
  id: string;
  label: string;
  value: number;
  color: string;
  note: string;
}

interface SpeciesCompareChartProps {
  bars: CompareBar[];
  unit: string;
  /** Log scale is the point of this chart (values span orders of
   * magnitude, e.g. 104 vs 86,000,000,000) -- see docs/23. */
  minValue?: number;
}

const CHART_HEIGHT_PER_BAR = 34;
const BAR_THICKNESS = 18; // <= 24px per the dataviz skill's bar mark spec
const LEFT_LABEL_WIDTH = 132;
const RIGHT_PADDING = 92;
const CHART_WIDTH = 520;

function formatValue(value: number): string {
  if (value >= 1_000_000_000) return `${(value / 1_000_000_000).toFixed(1)}십억`;
  if (value >= 100_000_000) return `${(value / 100_000_000).toFixed(1)}억`;
  if (value >= 10_000) return `${(value / 10_000).toFixed(1)}만`;
  return value.toLocaleString("ko-KR");
}

/** Horizontal log-scale bar chart -- built for this page's specific need
 * (3 species, values spanning many orders of magnitude) rather than as a
 * generic chart primitive. Hover shows the full source/citation note per
 * bar (dataviz skill's "per-mark hover tooltip on bar" requirement); values
 * are also always direct-labeled so identity/magnitude never depend on
 * hover or color alone. */
export function SpeciesCompareChart({ bars, unit, minValue = 1 }: SpeciesCompareChartProps) {
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  const plottable = bars.filter((b) => b.value > 0);
  const maxLog = Math.max(...plottable.map((b) => Math.log10(b.value)), Math.log10(minValue) + 1);
  const minLog = Math.log10(minValue);
  const plotWidth = CHART_WIDTH - LEFT_LABEL_WIDTH - RIGHT_PADDING;

  function xFor(value: number): number {
    const log = Math.log10(Math.max(value, minValue));
    return ((log - minLog) / (maxLog - minLog)) * plotWidth;
  }

  const hovered = bars.find((b) => b.id === hoveredId) ?? null;

  return (
    <div className="compare-chart">
      <svg width={CHART_WIDTH} height={bars.length * CHART_HEIGHT_PER_BAR + 24} role="img" aria-label={`종별 ${unit} 로그축 비교`}>
        {/* hairline baseline -- recessive, one step off surface, per mark spec */}
        <line
          x1={LEFT_LABEL_WIDTH}
          x2={LEFT_LABEL_WIDTH}
          y1={4}
          y2={bars.length * CHART_HEIGHT_PER_BAR + 4}
          stroke="var(--line)"
          strokeWidth={1}
        />
        {bars.map((bar, i) => {
          const y = i * CHART_HEIGHT_PER_BAR + 12;
          const w = bar.value > 0 ? Math.max(xFor(bar.value), 2) : 0;
          return (
            <g
              key={bar.id}
              onMouseEnter={() => setHoveredId(bar.id)}
              onMouseLeave={() => setHoveredId((cur) => (cur === bar.id ? null : cur))}
              style={{ cursor: "default" }}
            >
              <text x={LEFT_LABEL_WIDTH - 10} y={y + BAR_THICKNESS / 2 + 4} textAnchor="end" fill="var(--ink)" fontSize={10} fontFamily="var(--font-dm-mono)">
                {bar.label}
              </text>
              {bar.value > 0 ? (
                <rect x={LEFT_LABEL_WIDTH} y={y} width={w} height={BAR_THICKNESS} rx={4} fill={bar.color} opacity={hoveredId && hoveredId !== bar.id ? 0.55 : 1} />
              ) : (
                <text x={LEFT_LABEL_WIDTH} y={y + BAR_THICKNESS / 2 + 4} fill="var(--muted)" fontSize={9} fontFamily="var(--font-dm-mono)">
                  데이터 없음
                </text>
              )}
              {bar.value > 0 && (
                <text x={LEFT_LABEL_WIDTH + w + 8} y={y + BAR_THICKNESS / 2 + 4} fill="var(--muted)" fontSize={9} fontFamily="var(--font-dm-mono)">
                  {formatValue(bar.value)}
                  {unit}
                </text>
              )}
            </g>
          );
        })}
      </svg>
      <div className="compare-chart-tooltip" aria-live="polite">
        {hovered ? (
          <>
            <b style={{ color: hovered.color }}>{hovered.label}</b> {hovered.note}
          </>
        ) : (
          <span className="compare-chart-hint">막대에 마우스를 올리면 출처/근거가 표시됩니다.</span>
        )}
      </div>
    </div>
  );
}
