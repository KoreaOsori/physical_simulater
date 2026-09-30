import Link from "next/link";

/** Landing page for /human. Unlike C. elegans/Drosophila, humans have no
 * single "connectome" the same way — see backend/app/data/sources/human/
 * SOURCES.md for why 커넥톰 and 게놈 are two structurally different kinds of
 * real data, each getting its own branch rather than one shared page. */
export function HumanIndexPage() {
  return (
    <main className="lab-shell">
      <header className="topbar">
        <div className="brand">
          <b>∿</b> 신경 / <strong>인간 연구소</strong>
          <i>β</i>
        </div>
        <div className="specimen-title">
          <span>표본</span>
          <strong>인간 (Homo sapiens)</strong>
          <em>커넥톰 · 게놈 선택</em>
        </div>
        <div className="top-status">
          <Link href="/" className="species-switch">
            ← 종 전환: 예쁜꼬마선충
          </Link>
          <Link href="/fly" className="species-switch">
            종 전환: 초파리 →
          </Link>
          <Link href="/compare" className="species-switch">
            종간 비교
          </Link>
          <Link href="/lab" className="species-switch">
            연구소
          </Link>
        </div>
      </header>
      <section className="circuit-index">
        <p className="circuit-index-intro">
          인간은 웜/초파리처럼 뇌 전체를 뉴런 단위로 재구성한 지도가 존재하지 않습니다(860억
          뉴런 전체 EM 재구성은 기술적으로 불가능). 그래서 실재하는 두 가지 서로 다른 종류의
          데이터를 각각 정직하게 보여줍니다 — 뇌 영역 간 거시적 연결(커넥톰)과, 실제 염색체 위의
          유전자 지도(게놈).
        </p>
        <div className="circuit-cards">
          <Link href="/human/connectome" className="circuit-card">
            <strong>커넥톰</strong>
            <em>거시 영역 네트워크 + 실제 미시 샘플(H01)</em>
            <p>Schaefer 400 파셀레이션 시각 네트워크(실측 MRI 연결성) + 인간 대뇌피질 실제 EM 재구성 샘플</p>
          </Link>
          <Link href="/human/genome" className="circuit-card">
            <strong>게놈</strong>
            <em>염색체 지도 · 신경계 유전자 511개</em>
            <p>실제 염색체 위치·기능 주석 + BDNF 활동의존적 발현 경로 시뮬레이션</p>
          </Link>
        </div>
      </section>
    </main>
  );
}
