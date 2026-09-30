export interface ResearchTrend {
  id: string;
  title: string;
  year: string;
  venue: string;
  summary: string;
  relevance: string;
  url: string;
}

/**
 * Curated (not auto-fetched) list of real, cited recent C. elegans /
 * connectome-adjacent research. Gathered via web search 2026-09-15 — see
 * docs/06-neuron-ontology-and-trends.md for the queries used. This is meant
 * as a jumping-off point for "what's still unsolved / where could this
 * project's next idea come from", not a comprehensive literature review —
 * update it as new work becomes relevant.
 */
export const RESEARCH_TRENDS: ResearchTrend[] = [
  {
    id: "connectome-activity-bridge",
    title: "Bridging the gap between the connectome and whole-brain activity in C. elegans",
    year: "2025",
    venue: "bioRxiv / PMC",
    summary:
      "커넥톰(배선도)만으로는 실제 신경 활동을 예측하기 어렵다는 문제를, 단일 뉴런 광유전학 자극 + 전뇌 활동 기록 데이터로 보정한 '커넥톰 제약 동역학 모델'로 좁히려는 시도.",
    relevance:
      "이 프로젝트의 HH 시뮬레이션이 겪는 것과 같은 문제(연결 구조는 실제인데 활동 패턴은 근사)를 정면으로 다룸 — 향후 시냅스 가중치 보정에 참고할 만함.",
    url: "https://pmc.ncbi.nlm.nih.gov/articles/PMC12485687/",
  },
  {
    id: "brain-emulation-report",
    title: "State of Brain Emulation Report 2025",
    year: "2025",
    venue: "arXiv",
    summary:
      "C. elegans를 포함해 전뇌/전개체 에뮬레이션 분야 전반의 현재 위치를 정리한 서베이. OpenWorm 계열 프로젝트가 마주한 기술적 한계(전기생리 데이터 부족, 신경-근육-환경 피드백 루프 미완성 등)를 조망.",
    relevance: "이 프로젝트가 '어디까지 왔고 무엇이 남았는지'를 업계 전체 맥락에서 가늠하는 데 유용.",
    url: "https://arxiv.org/pdf/2510.15745",
  },
  {
    id: "sexual-dimorphism-single-neuron",
    title: "Decoding sexual dimorphism of the sex-shared nervous system at single-neuron resolution",
    year: "2025",
    venue: "Science Advances",
    summary: "암수 공유 신경계(302개 커넥톰의 기반)조차 개체 성별에 따라 단일 뉴런 수준에서 미세한 차이가 있음을 규명.",
    relevance:
      "이 프로젝트가 쓰는 '표준' 커넥톰(N2 야생형 자웅동체)도 하나의 스냅샷일 뿐, 실제로는 변이가 있다는 점을 상기시켜줌 — 데이터 한계 섹션에 참고.",
    url: "https://www.sciencedirect.com/science/article/pii/S2667237524003540",
  },
  {
    id: "unified-whole-brain-imaging",
    title: "Unifying community whole-brain imaging datasets enables robust neuron identification",
    year: "2024",
    venue: "Cell Reports Methods",
    summary: "여러 연구실의 전뇌 활동 이미징 데이터를 통합해 뉴런을 자동으로 식별하고, 뉴런 위치를 결정하는 요인을 분석.",
    relevance: "장기적으로 '실제 활동 기록 데이터'를 이 시뮬레이터에 입력으로 연결하고 싶다면 시작점이 될 자료.",
    url: "https://www.sciencedirect.com/science/article/pii/S2667237524003540",
  },
  {
    id: "liquid-neural-networks",
    title: "Liquid Neural Networks (Hasani et al., MIT CSAIL)",
    year: "2021~ (지속 연구 중)",
    venue: "MIT CSAIL / Nature Machine Intelligence 등",
    summary:
      "C. elegans의 302개 뉴런 신경회로 구조에서 착안해, 훨씬 적은 파라미터로 연속시간 동역학을 학습하는 AI 아키텍처. 드론·자율주행 등 엣지 AI에 실사용 중.",
    relevance:
      "'실제 생물 신경망 구조 → AI 아키텍처'로 인사이트가 흘러간 대표 사례. 이 프로젝트의 반대 방향(AI/시뮬레이션 기법 → 생물학적 시뮬레이터 개선)도 가능할지 참고할 만함.",
    url: "https://www.csail.mit.edu/news/liquid-machine-learning-system-adapts-changing-conditions",
  },
  {
    id: "openworm-feedback-limitation",
    title: "OpenWorm: 신경-근육-환경 피드백 루프 미완성 (지속 과제)",
    year: "진행 중",
    venue: "OpenWorm Project (Sibernetic / Geppetto)",
    summary:
      "OpenWorm 자체도 '신경 시뮬레이션 → 근육 → 물리 → (환경 반응이 다시 신경계로 피드백)'의 양방향 루프를 아직 완전히 구현하지 못했다고 명시하고 있음.",
    relevance:
      "이 프로젝트가 다음 단계로 고려 중인 '운동역학/물리 반영'이 OpenWorm도 아직 풀지 못한 어려운 문제라는 것 — 기대치 조정 및 단계적 접근의 근거.",
    url: "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4697589/",
  },
];
