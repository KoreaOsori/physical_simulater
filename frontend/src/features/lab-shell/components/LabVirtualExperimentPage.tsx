"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";

import { fetchConnectome, postLabVirtualExperiment } from "@/shared/lib/api-client";
import type { Connectome, Direction, Neuron, NeuronType } from "@/types/connectome";
import type { VirtualExperimentResponse } from "@/types/lab";

const DIRECTION_LABEL: Record<string, string> = {
  forward: "전진",
  reverse: "후진",
  left: "좌회전",
  right: "우회전",
};

const TYPE_LABEL: Record<NeuronType, string> = {
  sensory: "감각뉴런",
  inter: "중간뉴런",
  motor: "운동뉴런",
  unknown: "미분류",
};

/** 연구소(Lab) — 시뮬레이션 가상 실험실 (docs/35). 이미 있는 웜 HH
 * 시뮬레이션 엔진을 재사용해, AblationPanel의 7개 고전 절제 연구로 제한되지
 * 않고 실제 302개 뉴런 중 어떤 조합이든 자유롭게 억제해보고 결과를
 * 관찰한다 — 결과는 실제 시뮬레이션 출력이지만, 그 조합 자체가 문헌으로
 * 검증된 적은 없을 수 있다는 걸 항상 명시한다. */
export function LabVirtualExperimentPage() {
  const [connectome, setConnectome] = useState<Connectome | null>(null);
  const [filter, setFilter] = useState("");
  const [silencedIds, setSilencedIds] = useState<Set<string>>(new Set());
  const [direction, setDirection] = useState<Direction>("forward");
  const [result, setResult] = useState<VirtualExperimentResponse | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [connectomeError, setConnectomeError] = useState<string | null>(null);

  useEffect(() => {
    fetchConnectome()
      .then(setConnectome)
      .catch((err: unknown) => {
        // 실제 버그: 실패하면 콘솔에만 찍히고 화면엔 아무 설명 없이
        // 뉴런 선택 목록이 그냥 비어 있었다 -- 사용자는 왜 아무것도 안
        // 뜨는지 알 방법이 없었음.
        console.error("Failed to load worm connectome", err);
        setConnectomeError("뉴런 목록을 불러오지 못했습니다 — 페이지를 새로고침해보세요.");
      });
  }, []);

  const neuronsByType = useMemo(() => {
    if (!connectome) return {} as Record<NeuronType, Neuron[]>;
    const q = filter.trim().toLowerCase();
    const filtered = q ? connectome.neurons.filter((n) => n.id.toLowerCase().includes(q) || n.name.toLowerCase().includes(q)) : connectome.neurons;
    const groups: Record<string, Neuron[]> = {};
    for (const n of filtered) {
      (groups[n.type] ??= []).push(n);
    }
    return groups as Record<NeuronType, Neuron[]>;
  }, [connectome, filter]);

  const toggleNeuron = (id: string) => {
    setSilencedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const runExperiment = async () => {
    setRunning(true);
    setError(null);
    try {
      const response = await postLabVirtualExperiment({ direction, silenced_neuron_ids: [...silencedIds] });
      setResult(response);
    } catch (err: unknown) {
      console.error("Failed to run virtual experiment", err);
      setError("실험을 돌리지 못했습니다 — 잠시 후 다시 시도해주세요.");
    } finally {
      setRunning(false);
    }
  };

  return (
    <main className="lab-shell">
      <header className="topbar">
        <div className="brand">
          <b>∿</b> 신경 / <strong>연구소</strong>
          <i>β</i>
        </div>
        <div className="specimen-title">
          <span>탐구</span>
          <strong>시뮬레이션 가상 실험실</strong>
          <em>예쁜꼬마선충 · 자유 억제 조합</em>
        </div>
        <div className="top-status">
          <Link href="/lab" className="species-switch">
            ← 연구소
          </Link>
        </div>
      </header>
      <section className="lab-content">
        <div className="lab-honesty-banner">
          이 결과는 실제 생물학적 관찰이 아니라 이 프로젝트의 시뮬레이션(Hodgkin-Huxley 모델) 결과입니다. 고른
          뉴런 조합이 실제 문헌으로 검증된 적 없을 수 있습니다 — 가설을 만들어보는 도구입니다. 실제 웜 페이지의
          상태(습관화 등)에는 영향을 주지 않습니다.
        </div>

        <div className="lab-experiment-layout">
          <div className="lab-experiment-picker">
            <div className="network-switch lab-species-switch">
              {Object.keys(DIRECTION_LABEL).map((d) => (
                <button key={d} type="button" aria-pressed={direction === d} onClick={() => setDirection(d as Direction)}>
                  {DIRECTION_LABEL[d]}
                </button>
              ))}
            </div>
            <input
              type="text"
              className="lab-neuron-filter"
              placeholder="뉴런 id/이름 검색…"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
            />
            {connectomeError && <p className="panel-copy">{connectomeError}</p>}
            {!connectome && !connectomeError && <p className="panel-copy">뉴런 목록을 불러오는 중…</p>}
            <div className="lab-neuron-groups">
              {(Object.keys(TYPE_LABEL) as NeuronType[]).map((type) => {
                const neurons = neuronsByType[type] ?? [];
                if (neurons.length === 0) return null;
                return (
                  <div key={type} className="disorder-group">
                    <small>
                      {TYPE_LABEL[type]} ({neurons.length})
                    </small>
                    <div className="lab-neuron-chip-list">
                      {neurons.map((n) => (
                        <button
                          key={n.id}
                          type="button"
                          aria-pressed={silencedIds.has(n.id)}
                          className="lab-neuron-chip"
                          onClick={() => toggleNeuron(n.id)}
                        >
                          {n.id}
                        </button>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
            <div className="lab-experiment-actions">
              <span>{silencedIds.size}개 억제 선택됨</span>
              <button type="button" onClick={() => setSilencedIds(new Set())} disabled={silencedIds.size === 0}>
                선택 초기화
              </button>
              <button type="button" onClick={() => void runExperiment()} disabled={running}>
                {running ? "실행 중…" : "가상 실험 실행"}
              </button>
            </div>
            {error && <p className="panel-copy">{error}</p>}
          </div>

          <div className="lab-experiment-result">{result ? <ExperimentResultView result={result} /> : <p className="panel-copy">왼쪽에서 뉴런을 골라 억제하고 방향을 선택한 뒤 실행해보세요.</p>}</div>
        </div>
      </section>
    </main>
  );
}

function ExperimentResultView({ result }: { result: VirtualExperimentResponse }) {
  return (
    <>
      <div className="lab-metrics-grid">
        <div className="lab-metric">
          <strong>{result.baseline_neurons_fired.length}</strong>
          <span>기준선 발화 뉴런 수</span>
        </div>
        <div className="lab-metric">
          <strong>{result.experiment_neurons_fired.length}</strong>
          <span>실험 조건 발화 뉴런 수</span>
        </div>
        <div className="lab-metric">
          <strong>{result.silenced_but_would_have_fired.length}</strong>
          <span>실제로 영향받은 억제 뉴런</span>
          <em>기준선에서는 발화했지만 이번엔 억제된 것</em>
        </div>
      </div>

      {result.silenced_but_would_have_fired.length > 0 ? (
        <div className="disorder-group">
          <small>이 조합이 실제로 바꾼 것</small>
          <div className="lab-neuron-chip-list">
            {result.silenced_but_would_have_fired.map((id) => (
              <span key={id} className="lab-candidate-badge candidate">
                {id}
              </span>
            ))}
          </div>
        </div>
      ) : (
        <p className="panel-copy">
          이 조합은 기준선과 비교해 발화 패턴에 눈에 띄는 차이를 만들지 않았습니다 — 그 자체로도 실제 관찰입니다.
        </p>
      )}

      <div className="disorder-group">
        <small>실험 조건 이벤트 로그 ({result.experiment_events.length}개)</small>
        <div className="lab-event-log">
          {result.experiment_events.map((e, i) => (
            <div key={i} className="lab-event-row">
              <span className="lab-candidate-score">{e.t_ms.toFixed(1)}ms</span>
              <span>{e.message}</span>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}
