import Link from "next/link";

/** Landing page for /human/connectome — macro (region network) and micro
 * (real EM sample) are deliberately separate pages, not a click-through from
 * one into the other, since the micro sample's real anatomical location
 * (temporal cortex) doesn't match the macro page's network (visual) — see
 * backend/app/data/sources/human/SOURCES.md for why that link isn't faked. */
export function HumanConnectomeIndexPage() {
  return (
    <main className="lab-shell">
      <header className="topbar">
        <div className="brand">
          <b>∿</b> 신경 / <strong>인간 연구소</strong>
          <i>β</i>
        </div>
        <div className="specimen-title">
          <span>표본</span>
          <strong>인간 / 커넥톰</strong>
          <em>거시 · 미시 스케일 선택</em>
        </div>
        <div className="top-status">
          <Link href="/human" className="species-switch">
            ↑ 인간 홈
          </Link>
        </div>
      </header>
      <section className="circuit-index">
        <p className="circuit-index-intro">
          두 스케일은 서로 다른 실제 데이터셋이며 같은 것의 확대/축소가 아닙니다 — 거시
          네트워크는 시각 관련 뇌 영역, 미시 샘플은 측두엽의 실제 재구성 조각입니다.
        </p>
        <div className="circuit-cards">
          <Link href="/human/connectome/macro" className="circuit-card">
            <strong>거시 · 시각 네트워크</strong>
            <em>Schaefer 400 · 61개 영역 · 실측 MRI 연결성</em>
            <p>확산 MRI 트랙토그래피 기반 뇌 영역간 합의 연결성(HCP, 33명 피험자)</p>
          </Link>
          <Link href="/human/connectome/micro" className="circuit-card">
            <strong>미시 · 실제 피질 샘플 (측두엽)</strong>
            <em>H01 · 실제 뉴런 104개 · 나노미터 EM 재구성</em>
            <p>간질 수술로 얻은 인간 측두엽 조직 약 1mm³의 실제 재구성 뉴런 형태</p>
          </Link>
        </div>
      </section>
    </main>
  );
}
