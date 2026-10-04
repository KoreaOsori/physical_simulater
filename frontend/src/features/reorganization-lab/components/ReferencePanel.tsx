"use client";

import { useState } from "react";

import type { ReorgReference, ReorgStrategy } from "@/types/lab";

import { STRATEGY_COLOR, STRATEGY_SHORT } from "../lib/colors";

/** 스크립트로 미리 계산한 참고 결과(docs/52): ① 손상 기전 혼합별 최선 전략 지도(삼각형 = W1·W2·W3 혼합 비율)
 * ② 귀무 연결망 분포에서 실제 뇌의 이점이 어디쯤인지. 색 + 한 글자 약칭(색만으로 구분하지 않음). */

const TW = 300;
const TH = 270;

export function ReferencePanel({ reference, labels }: { reference: ReorgReference; labels: Record<ReorgStrategy, string> }) {
  const [hover, setHover] = useState<number | null>(null);
  const tri = (reference.strategy_map ?? []).filter((c) => (c.w[3] ?? 0) === 0);
  const w4 = (reference.strategy_map ?? []).filter((c) => (c.w[3] ?? 0) > 0);
  // 꼭짓점: W1 위, W2 왼쪽 아래, W3 오른쪽 아래
  const P = { w1: [TW / 2, 40], w2: [30, TH - 34], w3: [TW - 30, TH - 34] };
  const pos = (w: number[]) => [w[0] * P.w1[0] + w[1] * P.w2[0] + w[2] * P.w3[0], w[0] * P.w1[1] + w[1] * P.w2[1] + w[2] * P.w3[1]];
  const used = Array.from(new Set((reference.strategy_map ?? []).map((c) => c.best_effT as ReorgStrategy)));
  const hc = hover !== null ? tri[hover] : null;

  return (
    <div className="reorg-ref">
      {tri.length > 0 && (
        <figure className="reorg-ref-map">
          <figcaption>
            <strong>손상 기전 혼합별 최선 전략</strong>
            <span>10시기 뒤 전역 효율 기준 · 국소 병변 9개 평균</span>
          </figcaption>
          <svg width={TW} height={TH} role="img" aria-label="손상 기전 혼합 비율에 따른 최선 재조직 전략">
            <polygon points={[P.w1, P.w2, P.w3].map((p) => p.join(",")).join(" ")} className="reorg-ref-tri" />
            <text x={P.w1[0]} y={14} textAnchor="middle" className="vo-chart-tick">
              W1 과부하(상대)
            </text>
            <text x={P.w2[0] - 10} y={TH - 12} className="vo-chart-tick">
              W2 활동(절대)
            </text>
            <text x={P.w3[0] + 10} y={TH - 12} textAnchor="end" className="vo-chart-tick">
              W3 무작위
            </text>
            {tri.map((c, i) => {
              const [x, y] = pos(c.w);
              const s = c.best_effT as ReorgStrategy;
              return (
                <g key={i} onPointerEnter={() => setHover(i)} onPointerLeave={() => setHover(null)}>
                  <circle cx={x} cy={y} r={hover === i ? 13 : 11} fill={STRATEGY_COLOR[s]} className="reorg-ref-cell" />
                  <text x={x} y={y + 4} textAnchor="middle" className="reorg-ref-cell-label">
                    {STRATEGY_SHORT[s]}
                  </text>
                </g>
              );
            })}
          </svg>
          <div className="vo-chart-legend reorg-ref-legend">
            {used.map((s) => (
              <span key={s}>
                <i style={{ background: STRATEGY_COLOR[s] }} />
                {STRATEGY_SHORT[s]} {labels[s]}
              </span>
            ))}
          </div>
          <p className="reorg-map-tip">
            {hc
              ? `W1 ${(hc.w[0] * 100).toFixed(0)}% · W2 ${(hc.w[1] * 100).toFixed(0)}% · W3 ${(hc.w[2] * 100).toFixed(0)}% → ` +
                Object.entries(hc.table)
                  .sort((a, b) => b[1].effT - a[1].effT)
                  .slice(0, 3)
                  .map(([s, v]) => `${labels[s as ReorgStrategy]} ${v.effT.toFixed(4)}`)
                  .join(" > ")
              : "점에 마우스를 올리면 상위 3개 전략의 10시기 뒤 효율을 봅니다."}
          </p>
          {w4.length > 0 && (
            <ul className="reorg-ref-w4">
              {w4.map((c, i) => (
                <li key={i}>
                  W4 단절 {(c.w[3] * 100).toFixed(0)}%{c.w[0] > 0 ? ` + W1 ${(c.w[0] * 100).toFixed(0)}%` : ""}
                  {c.w[1] > 0 ? ` + W2 ${(c.w[1] * 100).toFixed(0)}%` : ""} → <b>{labels[c.best_effT as ReorgStrategy]}</b>
                </li>
              ))}
            </ul>
          )}
        </figure>
      )}
      {reference.null_test && (
        <div className="reorg-ref-null">
          <strong>귀무 연결망 분포 대비 실제 뇌(정상 부하 지도 기반 − 균등 분산, 연쇄 생존)</strong>
          {Object.entries(reference.null_test).map(([k, t]) => (
            <NullHistogram key={k} t={t} />
          ))}
        </div>
      )}
      {reference.notes && (
        <ul className="reorg-ref-notes">
          {reference.notes.map((n) => (
            <li key={n}>{n}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

function NullHistogram({ t }: { t: NonNullable<ReorgReference["null_test"]>[string] }) {
  const W = 300;
  const H = 90;
  const { edges, counts } = t.hist;
  const lo = Math.min(edges[0], t.real);
  const hi = Math.max(edges[edges.length - 1], t.real);
  const sx = (v: number) => 8 + ((v - lo) / (hi - lo || 1)) * (W - 16);
  const top = Math.max(...counts, 1);
  return (
    <figure className="reorg-ref-hist">
      <figcaption>
        {t.label} · 귀무 {t.n}개 · P(실제 &gt; 귀무) = {t.p_real_gt_null.toFixed(3)}
      </figcaption>
      <svg width={W} height={H} role="img" aria-label={`${t.label} 귀무 분포와 실제 값`}>
        {counts.map((c, i) => {
          const x0 = sx(edges[i]);
          const x1 = sx(edges[i + 1]);
          const h = (c / top) * (H - 26);
          return <rect key={i} x={x0 + 1} y={H - 16 - h} width={Math.max(1, x1 - x0 - 2)} height={h} rx={2} className="reorg-ref-bar" />;
        })}
        <line x1={sx(t.real)} x2={sx(t.real)} y1={4} y2={H - 16} className="reorg-ref-real" />
        <text x={Math.min(W - 4, sx(t.real) + 4)} y={12} textAnchor={sx(t.real) > W - 70 ? "end" : "start"} className="vo-chart-direct">
          실제 뇌 {t.real >= 0 ? "+" : ""}
          {t.real.toFixed(3)}
        </text>
        <text x={8} y={H - 3} className="vo-chart-tick">
          {lo.toFixed(2)}
        </text>
        <text x={W - 8} y={H - 3} textAnchor="end" className="vo-chart-tick">
          {hi.toFixed(2)}
        </text>
      </svg>
    </figure>
  );
}
