"use client";

import { useState } from "react";

import { RESEARCH_TRENDS } from "@/features/research-trends/data/trends";

/**
 * A standing spot for "what's happening in the field right now" — separate
 * from the rest of the tissue panel, which only describes what THIS
 * simulator implements. Curated links, not live-fetched; see trends.ts for
 * how these were gathered and when they were last refreshed.
 */
export function ResearchTrendsPanel() {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  return (
    <div className="trends-panel">
      <div className="trends-panel-head">
        <small>연구 동향 · 다른 인사이트</small>
        <p>
          이 시뮬레이터가 구현한 범위 밖에서, 최근 C. elegans/커넥톰 연구가 어디까지 왔는지 확인할 수 있는 참고
          목록입니다. 자동으로 갱신되지 않으며, 사람이 고른 큐레이션입니다.
        </p>
      </div>
      <div className="trends-list">
        {RESEARCH_TRENDS.map((trend) => {
          const isOpen = expandedId === trend.id;
          return (
            <article key={trend.id} className={isOpen ? "trend-item open" : "trend-item"}>
              <button type="button" onClick={() => setExpandedId(isOpen ? null : trend.id)}>
                <span className="trend-item-meta">
                  {trend.year} · {trend.venue}
                </span>
                <span className="trend-item-title">{trend.title}</span>
              </button>
              {isOpen && (
                <div className="trend-item-body">
                  <p>{trend.summary}</p>
                  <p className="trend-item-relevance">
                    <span>이 프로젝트와의 관련성</span> {trend.relevance}
                  </p>
                  <a href={trend.url} target="_blank" rel="noreferrer">
                    원문 보기 →
                  </a>
                </div>
              )}
            </article>
          );
        })}
      </div>
    </div>
  );
}
