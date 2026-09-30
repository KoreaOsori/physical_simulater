"use client";

import { useSimulationStore } from "@/store/simulation-store";

export function EventLog() {
  const logs = useSimulationStore((s) => s.logs);
  const setSelectedTissueId = useSimulationStore((s) => s.setSelectedTissueId);
  const connectionStatus = useSimulationStore((s) => s.connectionStatus);

  return (
    <aside className="panel log-panel">
      <div className="panel-head">
        03 / 이벤트 기록 <button type="button">⋯</button>
      </div>
      <div className="trace-status">
        <i style={{ background: connectionStatus === "open" ? "var(--lime)" : "#e08a5a" }} />
        {connectionStatus === "open" ? "기록 중" : connectionStatus === "connecting" ? "연결 중" : "연결 끊김"}
        <em>{logs.length}개 이벤트</em>
      </div>
      <div className="log-list">
        {logs.map((log) => (
          <article
            className="log"
            key={log.id}
            onClick={() => setSelectedTissueId(log.tag === "근육" ? "muscle" : "neurons")}
          >
            <time>{log.time}</time>
            <b className="tag">{log.tag}</b>
            <p>{log.message}</p>
          </article>
        ))}
      </div>
      <div className="trace-footer">
        버퍼 <span><i /></span> {Math.min(99, logs.length * 4)}%
      </div>
    </aside>
  );
}
