"use client";

import Link from "next/link";

import { FLY_CIRCUITS, type FlyCircuit } from "@/features/lab-shell/lib/fly-circuits";
import { useFlySimulationStore } from "@/store/fly-simulation-store";

interface FlyTopBarProps {
  circuit: FlyCircuit;
}

/** Links to the circuit-index page (not directly to sibling circuits) — with
 * only 2 circuits a direct "→ other circuit" shortcut made sense, but that
 * doesn't scale as more circuits get added (see fly-circuits.ts), so the
 * index page is the one hub for cross-circuit navigation instead. */
export function FlyTopBar({ circuit }: FlyTopBarProps) {
  const connectionStatus = useFlySimulationStore((s) => s.connectionStatus);
  const config = FLY_CIRCUITS[circuit];

  return (
    <header className="topbar">
      <div className="brand">
        <b>∿</b> 신경 / <strong>초파리 연구소</strong>
        <i>β</i>
      </div>
      <div className="specimen-title">
        <span>표본</span>
        <strong>{config.specimenTitle}</strong>
        <em>{config.specimenSubtitle}</em>
      </div>
      <div className="top-status">
        <Link href="/fly" className="species-switch">
          ↑ 회로 목록
        </Link>
        <Link href="/" className="species-switch">
          ← 종 전환: 예쁜꼬마선충
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
