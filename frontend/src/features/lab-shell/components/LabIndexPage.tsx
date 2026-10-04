import Link from "next/link";

/** 연구소(Lab) 랜딩 페이지 (docs/34+). 이 프로젝트의 나머지 부분("실제
 * 출처만" 확정 데이터/시뮬레이션)과 의도적으로 분리된 탐구 공간 — 실제
 * 데이터로부터 계산한 진짜 값을 다루지만, 해석은 검증된 사실이 아니라
 * 가설이라는 걸 이 페이지 자체가 먼저 밝힌다. 개인 로컬 전용, 배포 대상
 * 아님. */
export function LabIndexPage() {
  return (
    <main className="lab-shell">
      <header className="topbar">
        <div className="brand">
          <b>∿</b> 신경 / <strong>연구소</strong>
          <i>β</i>
        </div>
        <div className="specimen-title">
          <span>탐구 공간</span>
          <strong>가설 생성 · 실험적 기능</strong>
          <em>개인 로컬 전용</em>
        </div>
        <div className="top-status">
          <Link href="/" className="species-switch">
            ← 예쁜꼬마선충
          </Link>
          <Link href="/fly" className="species-switch">
            초파리
          </Link>
          <Link href="/human" className="species-switch">
            인간
          </Link>
          <Link href="/compare" className="species-switch">
            종간 비교
          </Link>
        </div>
      </header>
      <section className="circuit-index">
        <p className="circuit-index-intro lab-honesty-banner">
          이 프로젝트의 나머지 페이지는 전부 &ldquo;실제 출처만, 검증되지 않은 건 절대 지어내지 않는다&rdquo;는
          원칙을 지킵니다. 여기 연구소는 그 위에서 <b>가설을 만들어보는</b> 별도 공간입니다 — 실제 데이터로부터
          계산한 진짜 숫자를 다루지만, 그 해석은 검증된 사실이 아니라 이 프로젝트가 만들어본 가설입니다. 개인
          로컬 탐구용이라 도전적인 질문도 던져봅니다.
        </p>
        <div className="circuit-cards">
          <Link href="/lab/topology" className="circuit-card">
            <strong>네트워크 위상 분석</strong>
            <em>그래프 이론 기반 가설 생성기</em>
            <p>웜 전체 신경계·초파리 3개 회로·인간 거시 구조연결에 중심성·모듈성·작은세상성을 계산해, 고전 문헌에 아직 없는 후보를 찾아본다.</p>
          </Link>
          <Link href="/lab/virtual-experiment" className="circuit-card">
            <strong>시뮬레이션 가상 실험실</strong>
            <em>자유 뉴런 억제 조합 · 예쁜꼬마선충</em>
            <p>7개 고전 절제 연구로 제한되지 않고, 실제 302개 뉴런 중 어떤 조합이든 골라 억제해보고 실제 HH 시뮬레이션 결과를 관찰한다.</p>
          </Link>
          <Link href="/lab/explore-chat" className="circuit-card">
            <strong>탐구형 챗봇 모드</strong>
            <em>실시간 웹 검색 · 외부 자료</em>
            <p>인간 커넥톰 챗봇과 반대로 로컬 DB 밖으로 나가 실제 웹을 검색해 답한다 — 답변마다 실제 출처 링크가 함께 표시된다.</p>
          </Link>
          <Link href="/lab/gene-pathway" className="circuit-card">
            <strong>유전자 경로 후보 가설 탐색기</strong>
            <em>위치 후보 유전자 접근</em>
            <p>실제 염색체 위치 데이터로 BDNF·Arc 경로 유전자 주변의 물리적으로 가까운 실제 유전자 후보를 찾는다(실제 유전학 방법론).</p>
          </Link>
          <Link href="/lab/hypotheses" className="circuit-card">
            <strong>가설 노트</strong>
            <em>4개 도구를 조합한 실제 검증 기록</em>
            <p>위 도구들과 가상 개체 폐루프를 실제로 돌려 세운 가설 49개 — 지지됐든 기각됐든/혼재하든(예: 다중 질환 영역과 위상 중심성은 상관 없음, 무작위 회피는 &lsquo;새는&rsquo; 배제 구역을 만듦) 정직하게 기록한다.</p>
          </Link>
          <Link href="/lab/reorganization" className="circuit-card">
            <strong>손상-재조직 실험실 · 폐루프 재활</strong>
            <em>인간 거시 커넥톰 400영역 · 가설 H17</em>
            <p>병변을 고르고 재조직 전략과 손상 기전 혼합(W1~W4)을 바꿔 결과를 비교한다. 폐루프 탭에서는 매 시기 정상 부하 지도와의 차이를 재고 개입(연결 유도 또는 활동 조절)하는 재활을, 같은 예산의 개방 루프와 비교한다.</p>
          </Link>
          <Link href="/lab/virtual-worm" className="circuit-card">
            <strong>가상 예쁜꼬마선충 — 환경 폐루프</strong>
            <em>실제 302개 뉴런 커넥톰 · 실시간 감각-행동 순환</em>
            <p>명령 1개짜리 트레이스가 아니라, 유인물질 농도 기울기를 실제로 감각하고 그 결과로 실제로 이동하며 이동한 위치가 다시 감각 입력이 되는 진짜 폐루프(klinokinesis)를 처음으로 만들어본다.</p>
          </Link>
          <Link href="/lab/virtual-fly" className="circuit-card">
            <strong>가상 초파리 — 환경 폐루프</strong>
            <em>실제 hemibrain 후각 회로(~2,452개 뉴런) · MBON 밸런스 회피</em>
            <p>DA1(페로몬 cVA) 냄새 농도가 짙어질수록 실제 PN→KC→MBON01 경로가 활성화되고, MBON01(y5B&apos;2a) 발화가 회피 행동을 유도한다는 실제 문헌(Aso et al. 2014)을 그대로 따르는 폐루프.</p>
          </Link>
        </div>
      </section>
    </main>
  );
}
