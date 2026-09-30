"use client";

import Link from "next/link";

import { useSimulationStore } from "@/store/simulation-store";

export function TopBar() {
  const connectionStatus = useSimulationStore((s) => s.connectionStatus);

  return (
    <header className="topbar">
      <div className="brand">
        <b>∿</b> 신경 / <strong>선충 연구소</strong>
        <i>β</i>
      </div>
      <div className="specimen-title">
        <span>표본</span>
        <strong>예쁜꼬마선충 / N2 야생형</strong>
        <em>성체 자웅동체 · 1.01 mm</em>
      </div>
      <div className="top-status">
        <Link href="/fly" className="species-switch">
          종 전환: 초파리 →
        </Link>
        <Link href="/human" className="species-switch">
          종 전환: 인간 →
        </Link>
        <Link href="/compare" className="species-switch">
          종간 비교
        </Link>
        <Link href="/lab" className="species-switch">
          연구소
        </Link>
        <i style={{ background: connectionStatus === "open" ? "var(--lime)" : "#e08a5a" }} />
        {connectionStatus === "open" ? "실시간 시뮬레이션" : "연결 대기"} <b>로컬</b>
      </div>
    </header>
  );
}
