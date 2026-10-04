"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";

import { fetchReorgLabMeta, postClosedLoopRehab, postReorgLabRun } from "@/shared/lib/api-client";
import type {
  ClosedLoopMode,
  ClosedLoopResponse,
  ReorgLabMeta,
  ReorgLabResponse,
  ReorgMixture,
  ReorgStrategy,
} from "@/types/lab";

import { CONTROLLER_COLOR, CONTROLLER_LABEL, CONTROLLER_SHORT, REFERENCE_COLOR, STRATEGY_COLOR } from "../lib/colors";
import { BrainLoadMap } from "./BrainLoadMap";
import { EpochLineChart } from "./EpochLineChart";
import { ReferencePanel } from "./ReferencePanel";
import { ScheduleMode } from "./ScheduleMode";

type Tab = "lab" | "loop";

const PRESETS: { name: string; m: ReorgMixture }[] = [
  { name: "W1 과부하(상대)", m: { w1: 1, w2: 0, w3: 0, w4: 0 } },
  { name: "W2 활동(절대)", m: { w1: 0, w2: 1, w3: 0, w4: 0 } },
  { name: "W3 무작위", m: { w1: 0, w2: 0, w3: 1, w4: 0 } },
  { name: "W4 단절", m: { w1: 0, w2: 0, w3: 0, w4: 1 } },
  { name: "고른 혼합", m: { w1: 0.25, w2: 0.25, w3: 0.25, w4: 0.25 } },
];

const pct = (v: number) => `${(v * 100).toFixed(1)}%`;

/** 실행 중 경과 초. 0으로 되돌리기는 실행 버튼 핸들러에서(reset) -- effect 안에서 동기 setState를 하지 않는다. */
function useElapsed(running: boolean): [number, () => void] {
  const [s, setS] = useState(0);
  useEffect(() => {
    if (!running) return;
    const t = setInterval(() => setS((v) => v + 1), 1000);
    return () => clearInterval(t);
  }, [running]);
  return [s, () => setS(0)];
}

/** 연구소 — 손상-재조직 실험실과 폐루프 재활(docs/52). 가설 H17(정상 부하 지도 기반 재조직)을 직접 돌려 보는 도구. */
export function ReorgLabPage() {
  const [meta, setMeta] = useState<ReorgLabMeta | null>(null);
  const [metaError, setMetaError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("lab");
  const [lesionId, setLesionId] = useState("d0");
  const [mix, setMix] = useState<ReorgMixture>({ w1: 0.25, w2: 0.25, w3: 0.25, w4: 0.25 });
  const [epochs, setEpochs] = useState(10);
  const [reps, setReps] = useState(2);

  useEffect(() => {
    fetchReorgLabMeta()
      .then(setMeta)
      .catch((err: unknown) => {
        console.error("Failed to load reorganization lab meta", err);
        setMetaError("실험실 정보를 불러오지 못했습니다 — 백엔드가 켜져 있는지 확인하고 새로고침해보세요.");
      });
  }, []);

  const chooseTab = (t: Tab) => setTab(t);

  const total = mix.w1 + mix.w2 + mix.w3 + mix.w4 || 1;

  return (
    <main className="lab-shell">
      <header className="topbar">
        <div className="brand">
          <b>∿</b> 신경 / <strong>연구소</strong>
          <i>β</i>
        </div>
        <div className="specimen-title">
          <span>탐구</span>
          <strong>손상-재조직 실험실</strong>
          <em>인간 거시 구조 커넥톰 400영역 · 가설 H17</em>
        </div>
        <div className="top-status">
          <Link href="/lab/hypotheses" className="species-switch">
            가설 노트
          </Link>
          <Link href="/lab" className="species-switch">
            ← 연구소
          </Link>
        </div>
      </header>
      <section className="lab-content reorg-lab">
        <div className="lab-honesty-banner">{meta?.honesty_note ?? "집단 평균 구조 커넥톰 위의 계산 실험입니다. 환자 데이터가 아닙니다."}</div>
        <div className="reorg-hypothesis">
          <strong>H17 v2 · 정상 부하 지도 참조 재조직 가설</strong>
          <p>
            재조직은 정상 부하 분포를 그대로 복원할 수 없다. 손상으로 불가피한 부하 재배치가 참조 부하 지도(정상 집단 대표 커넥톰)에서{" "}
            <b>각 영역이 자기 정상 부하 대비 과도하게 벗어나지 않도록 제약</b>할 때, 실패 문턱이 정상 부하에 연동된 <b>문턱형(연쇄) 실패</b>에서
            강건성이 커진다. 대가로 효율·2차 타격 내성이 줄고, <b>활동량 누적 마모(W2)</b>에서는 불리하며, <b>점진형 과부하(W1)</b>에서는 허브 집중이
            더 낫다(docs/54). 단, 이 결론은 <b>새 연결 발아(이진) 모델</b>에서의 것이며, 기존 연결 강화(가중치) 모델에서는 균등 분산이 더 강했다(docs/56·57). 회복 기전이 강화 → 발아 순서라면 &lsquo;초기 분산 → 후기 정상 부하 지도 참조&rsquo;가 가장 균형 잡힌 절충이었다(H17 v3, docs/58).
          </p>
          <p className="reorg-hypothesis-note">
            &lsquo;정상 부하 지도 기반&rsquo; = docs/50-51의 headroom 전략. 여기서 &lsquo;용량&rsquo;은 실제 생물학적 용량이 아니라 정상 집단 대표(HCP 33명 합의) 커넥톰의 매개
            중심성 지도입니다 — 특정 개인의 정상 뇌가 아닙니다(검토 의견 8·9·17번).
          </p>
        </div>
        {metaError && <p className="lab-error">{metaError}</p>}
        {meta && (
          <>
            <div className="reorg-controls">
              <label>
                병변
                <select value={lesionId} onChange={(e) => setLesionId(e.target.value)}>
                  <optgroup label="국소 증후군">
                    {meta.lesions
                      .filter((l) => l.category === "focal")
                      .map((l) => (
                        <option key={l.id} value={l.id}>
                          {l.name} ({l.size}영역)
                        </option>
                      ))}
                  </optgroup>
                  <optgroup label="복합 질환(넓은 병변)">
                    {meta.lesions
                      .filter((l) => l.category !== "focal")
                      .map((l) => (
                        <option key={l.id} value={l.id}>
                          {l.name} ({l.size}영역)
                        </option>
                      ))}
                  </optgroup>
                </select>
              </label>
              <fieldset className="reorg-mix">
                <legend>손상 기전 혼합 (합계로 정규화)</legend>
                {(["w1", "w2", "w3", "w4"] as const).map((k) => (
                  <label key={k} title={meta.mechanisms[k]}>
                    <span>{meta.mechanisms[k].split(" -- ")[0]}</span>
                    <input type="range" min={0} max={1} step={0.05} value={mix[k]} onChange={(e) => setMix({ ...mix, [k]: Number(e.target.value) })} />
                    <em>{((mix[k] / total) * 100).toFixed(0)}%</em>
                  </label>
                ))}
                <div className="reorg-presets">
                  {PRESETS.map((p) => (
                    <button key={p.name} type="button" onClick={() => setMix(p.m)}>
                      {p.name}
                    </button>
                  ))}
                </div>
              </fieldset>
              <label>
                시기 수
                <input type="number" min={2} max={20} value={epochs} onChange={(e) => setEpochs(Math.max(2, Math.min(20, Number(e.target.value))))} />
              </label>
              <label>
                반복
                <input type="number" min={1} max={4} value={reps} onChange={(e) => setReps(Math.max(1, Math.min(4, Number(e.target.value))))} />
              </label>
            </div>
            <div className="network-switch lab-species-switch reorg-tabs" role="tablist">
              <button type="button" role="tab" aria-selected={tab === "lab"} onClick={() => chooseTab("lab")}>
                재조직 실험실
              </button>
              <button type="button" role="tab" aria-selected={tab === "loop"} onClick={() => chooseTab("loop")}>
                폐루프 재활
              </button>
            </div>
            {tab === "lab" ? (
              <LabTab meta={meta} lesionId={lesionId} mix={mix} epochs={epochs} reps={reps} />
            ) : (
              <LoopTab meta={meta} lesionId={lesionId} mix={mix} epochs={epochs} reps={reps} />
            )}
          </>
        )}
      </section>
    </main>
  );
}

function LabTab({ meta, lesionId, mix, epochs, reps }: { meta: ReorgLabMeta; lesionId: string; mix: ReorgMixture; epochs: number; reps: number }) {
  const [chosen, setChosen] = useState<Set<ReorgStrategy>>(new Set(meta.strategies));
  const [cascadeM, setCascadeM] = useState(1.2);
  const [tau, setTau] = useState(0.6);
  const [result, setResult] = useState<ReorgLabResponse | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [elapsed, resetElapsed] = useElapsed(running);

  const run = async () => {
    resetElapsed();
    setRunning(true);
    setError(null);
    try {
      const order = meta.strategies.filter((s) => chosen.has(s));
      setResult(await postReorgLabRun({ lesion_id: lesionId, strategies: order, epochs, reps, cascade_m: cascadeM, seed: 52, tau, ...mix }));
    } catch (err: unknown) {
      console.error("Failed to run reorganization lab", err);
      setError("실험을 돌리지 못했습니다 — 잠시 후 다시 시도해주세요.");
    } finally {
      setRunning(false);
    }
  };

  const series = useMemo(() => {
    if (!result) return [];
    return [
      ...result.results.map((r) => ({ key: r.strategy, name: meta.strategy_labels[r.strategy], color: STRATEGY_COLOR[r.strategy], values: r.wear_mean })),
      { key: "healthy", name: "정상 뇌(병변 없음)", color: REFERENCE_COLOR, values: result.healthy_wear, dashed: true },
    ];
  }, [result, meta]);

  const best = (key: "efficiency" | "loadmap_rho" | "cascade_survival", dir: 1 | -1 = 1) =>
    result ? result.results.reduce((a, b) => (dir * b[key] > dir * a[key] ? b : a)).strategy : null;
  const bestFinal = result ? result.results.reduce((a, b) => (b.wear_mean[b.wear_mean.length - 1] > a.wear_mean[a.wear_mean.length - 1] ? b : a)).strategy : null;

  return (
    <div className="reorg-tab">
      <div className="reorg-tab-controls">
        <div className="reorg-strategy-picks">
          {meta.strategies.map((s) => (
            <label key={s}>
              <input
                type="checkbox"
                checked={chosen.has(s)}
                onChange={() =>
                  setChosen((prev) => {
                    const next = new Set(prev);
                    if (next.has(s)) next.delete(s);
                    else next.add(s);
                    return next;
                  })
                }
              />
              <i style={{ background: STRATEGY_COLOR[s] }} />
              {meta.strategy_labels[s]}
            </label>
          ))}
        </div>
        {chosen.has("tau") && (
          <label title="자기 정상 용량 대비 부하 비율이 τ 이하인 영역 중 연결이 많은 곳(빠른 회복)에 붙이고, 없으면 비율이 가장 낮은 곳에 붙입니다. τ=0은 정상 부하 지도 기반, τ가 크면 허브 집중과 같습니다.">
            τ 여유선 {tau.toFixed(2)}
            <input type="range" min={0} max={2} step={0.05} value={tau} onChange={(e) => setTau(Number(e.target.value))} />
          </label>
        )}
        <label>
          연쇄 허용치 m
          <select value={cascadeM} onChange={(e) => setCascadeM(Number(e.target.value))}>
            {[0.9, 1.0, 1.1, 1.2, 1.3, 1.5].map((m) => (
              <option key={m} value={m}>
                정상 부하 × {m.toFixed(1)}
              </option>
            ))}
          </select>
        </label>
        <button type="button" className="lab-run-button" disabled={running || chosen.size === 0} onClick={run}>
          {running ? `계산 중… ${elapsed}초` : "실험 실행"}
        </button>
        <span className="reorg-hint">전략 6개·10시기·2회 기준 약 20~60초(실제 그래프 계산). τ 제약: 허용치를 모를 때 기대값 최적 ≈ 0.6, 문턱을 알면 그 아래 여유선(docs/55-56).</span>
      </div>
      {error && <p className="lab-error">{error}</p>}
      {result && (
        <>
          <p className="reorg-summary">
            {result.lesion_name} · 병변 {result.lesion_size}영역 · 잃은 연결 {result.edges_lost}개 · 정상 뇌 효율 {result.healthy_efficiency.toFixed(4)}
          </p>
          <div className="reorg-table-wrap">
            <table className="reorg-table">
              <thead>
                <tr>
                  <th>전략</th>
                  <th>새 연결</th>
                  <th title="재조직 직후 전역 효율(원래 400영역 기준)">재조직 직후 효율</th>
                  <th title="재조직 후 부하와 정상 부하 지도의 Spearman 상관">정상 부하 지도 충실도 ρ</th>
                  <th title="정상 부하 × 1.2를 넘는 생존 영역 비율">과부하 영역</th>
                  <th title="부하가 정상 부하 × m을 넘으면 즉시 실패하는 연쇄 모델">연쇄 생존</th>
                  <th>{epochs}시기 뒤 효율</th>
                </tr>
              </thead>
              <tbody>
                {result.results.map((r) => (
                  <tr key={r.strategy}>
                    <td>
                      <i style={{ background: STRATEGY_COLOR[r.strategy] }} />
                      {r.label}
                    </td>
                    <td>{r.edges_added}</td>
                    <td className={best("efficiency") === r.strategy ? "is-best" : ""}>{r.efficiency.toFixed(4)}</td>
                    <td className={best("loadmap_rho") === r.strategy ? "is-best" : ""}>{r.loadmap_rho.toFixed(3)}</td>
                    <td>{pct(r.overload_frac)}</td>
                    <td className={best("cascade_survival") === r.strategy ? "is-best" : ""}>{pct(r.cascade_survival)}</td>
                    <td className={bestFinal === r.strategy ? "is-best" : ""}>{r.wear_mean[r.wear_mean.length - 1].toFixed(4)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="reorg-hint">▲ 굵은 값 = 그 열의 최선. 재조직 없음은 새 연결이 없어 충실도가 높게 나옵니다(복원이 아니라 &lsquo;안 바꿈&rsquo;).</p>
          </div>
          <EpochLineChart title="마모 시기별 전역 효율(원래 400영역 기준)" series={series} format={(v) => v.toFixed(3)} />
        </>
      )}
      {meta.reference && <ReferencePanel reference={meta.reference} labels={meta.strategy_labels} />}
    </div>
  );
}

function LoopTab({ meta, lesionId, mix, epochs, reps }: { meta: ReorgLabMeta; lesionId: string; mix: ReorgMixture; epochs: number; reps: number }) {
  const [view, setView] = useState<"intervention" | "schedule">("intervention");
  const [mode, setMode] = useState<ClosedLoopMode>("connect");
  const [budget, setBudget] = useState(20);
  const [base, setBase] = useState<ReorgStrategy>("distributed");
  const [result, setResult] = useState<ClosedLoopResponse | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [elapsed, resetElapsed] = useElapsed(running);

  const run = async () => {
    resetElapsed();
    setRunning(true);
    setError(null);
    try {
      setResult(await postClosedLoopRehab({ lesion_id: lesionId, mode, budget, base_strategy: base, epochs, reps, seed: 52, ...mix }));
    } catch (err: unknown) {
      console.error("Failed to run closed-loop rehab", err);
      setError("폐루프 실험을 돌리지 못했습니다 — 잠시 후 다시 시도해주세요.");
    } finally {
      setRunning(false);
    }
  };

  const mk = (key: "efficiency" | "alive" | "deviation" | "overload") =>
    result
      ? result.traces.map((t) => ({ key: t.controller, name: CONTROLLER_LABEL[t.controller], short: CONTROLLER_SHORT[t.controller], color: CONTROLLER_COLOR[t.controller], values: t[key] }))
      : [];

  const final = (c: string, key: "efficiency" | "alive") => {
    const t = result?.traces.find((x) => x.controller === c);
    return t ? t[key][t[key].length - 1] : 0;
  };

  const viewSwitch = (
    <div className="network-switch lab-species-switch reorg-view-switch">
      <button type="button" aria-pressed={view === "intervention"} onClick={() => setView("intervention")}>
        개입 폐루프(연결 유도·활동 조절)
      </button>
      <button type="button" aria-pressed={view === "schedule"} onClick={() => setView("schedule")}>
        시기 맞춤 재조직(가중치 모델)
      </button>
    </div>
  );
  if (view === "schedule")
    return (
      <div className="reorg-tab">
        {viewSwitch}
        <ScheduleMode lesionId={lesionId} />
      </div>
    );

  return (
    <div className="reorg-tab">
      {viewSwitch}
      <div className="reorg-loop-explain">
        매 시기: <b>감지</b>(현재 영역별 부하 vs 정상 부하 지도) → <b>개입</b> → <b>마모</b>(위의 손상 기전 혼합). 같은 예산의 개방 루프(처음 한 번
        계획하고 그대로 실행)와 비교합니다. 개인별 정상 범위(μ, σ)가 생기면 감지 단계의 &lsquo;정상 대비 비율&rsquo;을 Z 점수로 바꿀 수 있습니다.
      </div>
      <div className="reorg-tab-controls">
        <div className="network-switch lab-species-switch">
          <button type="button" aria-pressed={mode === "connect"} onClick={() => setMode("connect")}>
            연결 유도(가소성)
          </button>
          <button type="button" aria-pressed={mode === "modulate"} onClick={() => setMode("modulate")}>
            활동 조절(TMS/BCI 유사)
          </button>
        </div>
        <label>
          {mode === "connect" ? "시기당 새 연결 수" : "시기당 자극 영역 수"}
          <input type="number" min={1} max={100} value={budget} onChange={(e) => setBudget(Math.max(1, Math.min(100, Number(e.target.value))))} />
        </label>
        {mode === "modulate" && (
          <label title="활동 조절은 구조를 바꾸지 않으므로, 환자가 이미 겪은 자연 재조직 위에서 개입합니다.">
            환자의 자연 재조직
            <select value={base} onChange={(e) => setBase(e.target.value as ReorgStrategy)}>
              {meta.strategies
                .filter((s) => s !== "tau")
                .map((s) => (
                  <option key={s} value={s}>
                    {meta.strategy_labels[s]}
                  </option>
                ))}
            </select>
          </label>
        )}
        <button type="button" className="lab-run-button" disabled={running} onClick={run}>
          {running ? `계산 중… ${elapsed}초` : "폐루프 실행"}
        </button>
      </div>
      <p className="reorg-hint">
        {mode === "connect"
          ? "연결 유도: 잃은 연결 수만큼 정상 부하 지도 기반 규칙으로 새 연결을 붙입니다. 폐루프는 매 시기 현재 부하를 다시 재고, 마모로 새로 잃은 영역의 이웃도 대상에 넣습니다(총 예산은 같음)."
          : "활동 조절: 정상 부하를 넘은 영역 상위 N곳의 부하를 용량까지(최대 50%) 낮춰 이웃의 여유분으로 넘깁니다(경로 재계산이 아닌 근사). 폐루프는 매 시기 대상을 다시 고르고, 개방 루프는 처음 고른 영역을 계속 자극합니다."}
      </p>
      {error && <p className="lab-error">{error}</p>}
      {result && (
        <>
          <div className="vo-stats">
            {(["none", "open", "closed"] as const).map((c) => (
              <div className="lab-metric" key={c}>
                <strong>{final(c, "efficiency").toFixed(4)}</strong>
                <span>{CONTROLLER_LABEL[c]}</span>
                <em>
                  최종 생존 {final(c, "alive").toFixed(1)}영역 · 개입 {result.traces.find((t) => t.controller === c)?.interventions.reduce((a, b) => a + b, 0).toFixed(0)}회
                </em>
              </div>
            ))}
          </div>
          <div className="vo-charts reorg-loop-charts">
            <EpochLineChart title="전역 효율(원래 400영역 기준)" series={mk("efficiency")} format={(v) => v.toFixed(3)} />
            <EpochLineChart title="살아 있는 영역 수" series={mk("alive")} format={(v) => v.toFixed(0)} />
            <EpochLineChart title="정상 부하 지도 이탈 |log(부하/정상 부하)|" series={mk("deviation")} format={(v) => v.toFixed(2)} />
            <EpochLineChart title="과부하 영역 비율(정상 부하 × 1.2 초과)" series={mk("overload")} format={(v) => `${(v * 100).toFixed(0)}%`} />
          </div>
          <div className="reorg-maps">
            <BrainLoadMap title="마지막 시기 · 개입 없음" regions={result.regions} pick="none" />
            <BrainLoadMap title="마지막 시기 · 폐루프" regions={result.regions} pick="closed" />
          </div>
          <p className="reorg-hint">지도는 첫 번째 반복의 마지막 시기 상태입니다(그래프는 반복 평균).</p>
        </>
      )}
    </div>
  );
}
