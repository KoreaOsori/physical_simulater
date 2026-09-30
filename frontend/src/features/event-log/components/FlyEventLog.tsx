"use client";

import { useFlySimulationStore } from "@/store/fly-simulation-store";

export function FlyEventLog() {
  const logs = useFlySimulationStore((s) => s.logs);
  const connectionStatus = useFlySimulationStore((s) => s.connectionStatus);

  return (
    <aside className="panel log-panel">
      <div className="panel-head">03 / 이벤트 기록</div>
      <div className="trace-status">
        <i style={{ background: connectionStatus === "open" ? "var(--lime)" : "#e08a5a" }} />
        {connectionStatus === "open" ? "기록 중" : connectionStatus === "connecting" ? "연결 중" : "연결 끊김"}
        <em>{logs.length}개 이벤트</em>
      </div>
      <div className="log-list">
        {logs.map((log) => (
          <article className="log" key={log.id}>
            <time>{log.time}</time>
            <b className="tag">{log.tag}</b>
            <p>{log.message}</p>
          </article>
        ))}
      </div>
    </aside>
  );
}
