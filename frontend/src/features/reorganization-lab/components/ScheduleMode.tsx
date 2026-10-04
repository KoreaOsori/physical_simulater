"use client";

import { useEffect, useState } from "react";

import { postPlasticitySchedule } from "@/shared/lib/api-client";
import type { PlasticityPolicy, PlasticityScheduleResponse } from "@/types/lab";

const POLICY_ORDER: PlasticityPolicy[] = ["matched", "tau0", "dist", "tau06", "mismatched", "conc"];
const POLICY_LABEL: Record<PlasticityPolicy, string> = {
  matched: "기전 인지 맞춤(강화=분산, 발아=τ0)",
  tau0: "정상 부하 지도 기반(τ=0)",
  dist: "균등 분산",
  tau06: "τ=0.6",
  mismatched: "엇갈림(강화=τ0, 발아=분산)",
  conc: "허브 집중",
};

const pct = (v: number) => `${(v * 100).toFixed(1)}%`;

/** 폐루프 탭 세 번째 모드(docs/58, H17-12). 회복 기전이 '강화 → 발아'로 바뀌는 가중치 모델에서, 매 단계 지금의 기전을 감지해
 * 전략을 바꾸는 '기전 인지' 정책을 고정 전략과 비교한다. 결과는 표(정확한 값) + 발아 비율 막대(일정 확인용). */
export function ScheduleMode({ lesionId }: { lesionId: string }) {
  const [schedule, setSchedule] = useState<"seq" | "ramp">("seq");
  const [chosen, setChosen] = useState<Set<PlasticityPolicy>>(new Set(POLICY_ORDER));
  const [result, setResult] = useState<PlasticityScheduleResponse | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (!running) return;
    const t = setInterval(() => setElapsed((v) => v + 1), 1000);
    return () => clearInterval(t);
  }, [running]);

  const run = async () => {
    setElapsed(0);
    setRunning(true);
    setError(null);
    try {
      setResult(await postPlasticitySchedule({ lesion_id: lesionId, schedule, policies: POLICY_ORDER.filter((p) => chosen.has(p)) }));
    } catch (err: unknown) {
      console.error("Failed to run plasticity schedule", err);
      setError("시기 맞춤 재조직을 돌리지 못했습니다 — 잠시 후 다시 시도해주세요.");
    } finally {
      setRunning(false);
    }
  };

  const rows = result?.results ?? [];
  const avg = (r: (typeof rows)[number]) => (r.end.casc_m12 + r.end.casc_m10) / 2;
  const best = (f: (r: (typeof rows)[number]) => number) => (rows.length ? rows.reduce((a, b) => (f(b) > f(a) ? b : a)).policy : null);
  const cols: { key: string; title: string; f: (r: (typeof rows)[number]) => number; fmt: (v: number) => string }[] = [
    { key: "m12m", title: "중간 연쇄 m1.2", f: (r) => r.mid.casc_m12, fmt: pct },
    { key: "m10m", title: "중간 연쇄 m1.0", f: (r) => r.mid.casc_m10, fmt: pct },
    { key: "m12e", title: "끝 연쇄 m1.2", f: (r) => r.end.casc_m12, fmt: pct },
    { key: "m10e", title: "끝 연쇄 m1.0", f: (r) => r.end.casc_m10, fmt: pct },
    { key: "avg", title: "끝 두 문턱 평균", f: avg, fmt: pct },
    { key: "eff", title: "끝 효율(정상 대비)", f: (r) => r.end.eff_rel, fmt: (v) => v.toFixed(3) },
  ];

  return (
    <div className="reorg-tab">
      <div className="reorg-loop-explain">
        가중치 모델(기존 연결 강화 + 새 연결 발아). 회복 초기에는 <b>기존 연결 강화</b>가, 뒤로 갈수록 <b>새 연결 발아</b>가 주가 된다고 봅니다(문헌의 시간 순서,
        docs/58). <b>기전 인지 맞춤</b> 정책은 매 단계 지금의 회복 기전을 보고 전략을 바꿉니다: 강화 단계에는 균등 분산(H17-11: 강화형에서 안전), 발아 단계에는
        정상 부하 지도 기반(발아형에서 안전). 위의 손상 기전 혼합·시기 수는 이 모드에서 쓰지 않습니다.
      </div>
      <div className="reorg-tab-controls">
        <div className="network-switch lab-species-switch">
          <button type="button" aria-pressed={schedule === "seq"} onClick={() => setSchedule("seq")}>
            순차(앞 50% 강화 → 뒤 50% 발아)
          </button>
          <button type="button" aria-pressed={schedule === "ramp"} onClick={() => setSchedule("ramp")}>
            점진(발아 비율 0 → 1)
          </button>
        </div>
        <div className="reorg-strategy-picks">
          {POLICY_ORDER.map((p) => (
            <label key={p}>
              <input
                type="checkbox"
                checked={chosen.has(p)}
                onChange={() =>
                  setChosen((prev) => {
                    const next = new Set(prev);
                    if (next.has(p)) next.delete(p);
                    else next.add(p);
                    return next;
                  })
                }
              />
              {POLICY_LABEL[p]}
            </label>
          ))}
        </div>
        <button type="button" className="lab-run-button" disabled={running || chosen.size === 0} onClick={run}>
          {running ? `계산 중… ${elapsed}초` : "시기 맞춤 재조직 실행"}
        </button>
        <span className="reorg-hint">정책 6개 기준 약 30~90초. 병변 12개 평균 결과는 H17-12(가설 노트).</span>
      </div>
      {error && <p className="lab-error">{error}</p>}
      {result && (
        <>
          <p className="reorg-summary">
            {result.lesion_name} · 재조직 {result.steps}단계 · {result.honesty_note}
          </p>
          <figure className="reorg-sprout-profile" aria-label="재조직 단계별 발아 비율">
            <figcaption>단계 10등분별 새 연결 발아 비율(나머지는 기존 연결 강화)</figcaption>
            <div className="reorg-sprout-bars">
              {result.sprout_fraction_by_decile.map((v, i) => (
                <span key={i} title={`${i * 10}~${(i + 1) * 10}% 단계: 발아 ${(v * 100).toFixed(0)}%`}>
                  <i style={{ height: `${Math.max(2, v * 100)}%` }} />
                  <em>{(v * 100).toFixed(0)}</em>
                </span>
              ))}
            </div>
          </figure>
          <div className="reorg-table-wrap">
            <table className="reorg-table">
              <thead>
                <tr>
                  <th>정책</th>
                  {cols.map((c) => (
                    <th key={c.key}>{c.title}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.policy}>
                    <td>{r.label}</td>
                    {cols.map((c) => (
                      <td key={c.key} className={best(c.f) === r.policy ? "is-best" : ""}>
                        {c.fmt(c.f(r))}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="reorg-hint">굵은 값 = 그 열의 최선. 병변 하나의 결과라 병변마다 달라질 수 있습니다(12개 평균: 맞춤이 두 문턱 평균 최선, 허브 집중이 연쇄 최하위).</p>
          </div>
        </>
      )}
    </div>
  );
}
