import Link from "next/link";

import { FLY_CIRCUITS } from "@/features/lab-shell/lib/fly-circuits";

/** Landing page for /fly — lists each hemibrain circuit subset as its own
 * page rather than loading all of them into one shared scene (see
 * fly-circuits.ts for why). Add a new circuit here by adding it to
 * FLY_CIRCUITS and giving it a route under app/fly/. */
export function FlyCircuitIndexPage() {
  return (
    <main className="lab-shell">
      <header className="topbar">
        <div className="brand">
          <b>∿</b> 신경 / <strong>초파리 연구소</strong>
          <i>β</i>
        </div>
        <div className="specimen-title">
          <span>표본</span>
          <strong>노랑초파리 (Drosophila melanogaster)</strong>
          <em>hemibrain v1.2 · 회로 서브셋 선택</em>
        </div>
        <div className="top-status">
          <Link href="/" className="species-switch">
            ← 종 전환: 예쁜꼬마선충
          </Link>
        </div>
      </header>
      <section className="circuit-index">
        <p className="circuit-index-intro">
          hemibrain v1.2 커넥톰에서 서로 다른 회로 서브셋을 각각 독립된 페이지로 확인합니다.
          공유 씬으로 합치는 대신 페이지를 나눠, 서브셋이 늘어나도 각 페이지의 렌더링·시뮬레이션
          부하는 그대로 유지됩니다 — 두 회로 사이의 실제 교차 시냅스는 백엔드 데이터셋에는
          그대로 남아 있습니다.
        </p>
        <div className="circuit-cards">
          {Object.values(FLY_CIRCUITS).map((config) => (
            <Link key={config.circuit} href={config.path} className="circuit-card">
              <strong>{config.navLabel}</strong>
              <em>{config.specimenSubtitle}</em>
              <p>{config.pipelineDescription}</p>
            </Link>
          ))}
        </div>
      </section>
    </main>
  );
}
