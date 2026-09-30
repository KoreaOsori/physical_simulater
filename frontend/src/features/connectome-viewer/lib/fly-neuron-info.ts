import type { Neuron } from "@/types/connectome";

/**
 * Real, sourced Korean descriptions for the Drosophila v2 (/fly) page,
 * mirroring neuron-info.ts's two-tier pattern for the C. elegans page:
 * (1) a description for every neuron's *circuit class* (real textbook-level
 * Drosophila neuroanatomy, not per-cell data — hemibrain's public flat files
 * carry no per-cell function/NT annotation, see SOURCES.md), plus (2) a
 * bonus curated one-liner, with a literature citation, for the handful of
 * specific cell *types* this project's command buttons actually stimulate
 * (backend/app/domain/schemas.py's OdorCommand/VisualCommand).
 *
 * Previously the fly tooltip only showed `neuron.name` (an instance name
 * like "LC4" or "KCab-ap1_R") with no functional text — this is the "뉴런
 * 툴팁 서술 보강" pass from the v2 roadmap checklist.
 */
const CIRCUIT_CLASS_DESCRIPTION: Record<string, string> = {
  "후각수용뉴런(ORN)":
    "후각수용체뉴런(Olfactory Receptor Neuron) — 더듬이의 냄새 수용체에서 축삭을 촉각엽(antennal lobe)까지 뻗어 사구체(glomerulus)에서 PN에 시냅스합니다. hemibrain은 central brain 위주로 촬영되어 세포체 대부분이 잘려나가 이 서브셋에는 극소수만 남아 있습니다.",
  "촉각엽 투사뉴런(PN)":
    "투사뉴런(Projection Neuron) — 촉각엽의 특정 사구체(하나의 냄새 수용체 유형에 대응)에서 입력을 받아 버섯체(mushroom body)와 측각엽(lateral horn)으로 냄새 정보를 중계합니다.",
  "버섯체 켄욘세포(KC)":
    "켄욘세포(Kenyon Cell) — 버섯체를 구성하는 고밀도 인터뉴런. 여러 PN으로부터 무작위에 가깝게 조합된 입력을 받아, 특정 냄새 조합에 희소하게(sparse) 반응하는 학습·연합 계층을 이룹니다.",
  "도파민성 뉴런(DAN)":
    "도파민성 뉴런(Dopaminergic Neuron, PAM/PPL 클러스터) — 버섯체 KC->MBON 시냅스에 보상/처벌 신호를 실어 시냅스 가소성(연합 학습)을 유도합니다. 세포유형 이름 자체가 신경전달물질이 도파민임을 뜻합니다.",
  "버섯체 출력뉴런(MBON)":
    "버섯체 출력뉴런(Mushroom Body Output Neuron) — 버섯체의 최종 출력 계층으로, KC 활동 패턴을 특정 행동(접근/회피) 유의성(valence) 신호로 변환해 하류 회로에 전달합니다.",
  "시각 투사뉴런(VPN)":
    "시각 투사뉴런(Visual Projection Neuron) — 로불라/로불라판(lobula/lobula plate)에서 특정 시각 특징(루밍, 소형 이동물체 등)을 검출해 중심뇌로 중계하는 출력 채널. hemibrain은 광수용체·medulla 내재뉴런은 촬영 범위 밖이라, 이 서브셋은 사실상 시엽의 '출력 경계'부터 시작합니다.",
  "하행뉴런(DN)":
    "하행뉴런(Descending Neuron) — 뇌에서 흉부신경절(VNC, 실제 비행/도약 운동뉴런이 있는 곳)로 신호를 내려보내는 출력 세포. hemibrain은 뇌만 촬영해 VNC의 실제 운동뉴런은 포함하지 않으므로, 이 서브셋에서는 DN이 회로의 '최종 출력 근사치' 역할을 합니다.",
  "고리뉴런(ER)":
    "고리뉴런(Ellipsoid-body Ring Neuron) — 타원체(ellipsoid body)로 시각 랜드마크 등 방향 관련 입력을 전달하는 것으로 알려진 뉴런. hemibrain은 이 입력의 상류(시각 경로)는 촬영 범위 밖이라, 이 서브셋에서는 사실상 '입력 경계'부터 시작합니다.",
  "나침반 고리뉴런(EPG/PEN/PEG/Delta7)":
    "나침반 고리뉴런 — 초파리의 머리 방향(heading)을 나타내는 활동 '범프(bump)'가 링을 따라 도는 링 어트랙터(ring attractor)를 구성하는 4종. EPG=헤딩 신호 자체, PEN=몸 회전에 따른 각속도 입력, PEG/Delta7=링 내부의 억제성 상호연결로 범프를 하나로 유지시킵니다. Hulse et al. 2021.",
  "헤딩-목표 통합뉴런(PFN)":
    "PFN(Protocerebral bridge-Fanshaped body-Noduli) — 나침반 링의 헤딩 신호와 내부 목표/상태 신호를 결합해 부채모양체(fan-shaped body)로 전달하는 투사뉴런. 여러 하위타입(PFNa/PFNd/PFNm 등)이 있습니다.",
  "조향 출력뉴런(PFL)":
    "PFL(Protocerebral bridge-Fanshaped body-Lateral accessory lobe) — 중심복합체의 대표적인 조향(steering) 출력뉴런. 헤딩과 목표 방향의 차이를 좌우 비대칭 신호로 변환해 회전 행동을 유도하는 것으로 출판되어 있습니다. Rayshubskiy et al. 2020; Mussells Pires et al. 2024.",
};

/** Bonus one-liners (with citation) for the specific cell types this
 * project's command buttons stimulate — matched by exact `cell_type` or, for
 * PN glomerulus types, a prefix match (e.g. "DA1_adPN" starts with "DA1_"). */
const CURATED_TYPE_INFO: { match: (cellType: string) => boolean; text: string }[] = [
  {
    match: (t) => t.startsWith("DA1_"),
    text: "DA1 사구체 PN — 수컷 페로몬(cVA, 11-cis-vaccenyl acetate)에 반응하는 것으로 잘 알려진 사구체. Kurtovic et al. 2007.",
  },
  { match: (t) => t.startsWith("DL2d_"), text: "DL2d 사구체 PN — 후각 자극 명령 버튼 중 하나로 사용되는 사구체." },
  { match: (t) => t.startsWith("VM5d_"), text: "VM5d 사구체 PN — 후각 자극 명령 버튼 중 하나로 사용되는 사구체." },
  { match: (t) => t.startsWith("DA2_"), text: "DA2 사구체 PN — 후각 자극 명령 버튼 중 하나로 사용되는 사구체." },
  {
    match: (t) => t === "LC4",
    text: "LC4 — 루밍(다가오는 물체) 검출기. Giant Fiber 도피 경로에 직접 입력하는 것으로 잘 알려진 시각투사뉴런. von Reyn et al. 2014.",
  },
  {
    match: (t) => t === "LC6",
    text: "LC6 — 루밍 검출기. LC4와 함께 Giant Fiber 도피 경로에 입력합니다. von Reyn et al. 2017.",
  },
  {
    match: (t) => t === "LPLC2",
    text: "LPLC2 — 양안 루밍(binocular looming) 검출기. Giant Fiber에 직접 시냅스하는 것으로 확인된 시각투사뉴런. Ache et al. 2019.",
  },
  {
    match: (t) => t === "LC9",
    text: "LC9 — 소형 이동물체 검출/추적에 관여하는 것으로 알려진 시각투사뉴런. Klapoetke et al. 2017.",
  },
  {
    match: (t) => t === "Giant Fiber",
    text: "Giant Fiber(GF) — 초파리에서 가장 잘 연구된 단일 식별 뉴런 중 하나. 루밍 자극을 감지해 도약(jump)·비행 도피 반응을 촉발하는 하행뉴런입니다.",
  },
  {
    match: (t) => t === "EPG",
    text: "EPG — 나침반 헤딩 신호를 담당하는 핵심 세포. 각 EPG 뉴런은 원판(protocerebral bridge)의 특정 웨지를 담당하며, 그 웨지 번호가 이 프로젝트의 헤딩 자극 커맨드 이름(예: L4, R4)입니다.",
  },
  {
    match: (t) => t === "PFL1",
    text: "PFL1 — 중심복합체의 조향 출력뉴런 하위타입 중 하나.",
  },
  {
    match: (t) => t === "PFL2",
    text: "PFL2 — 목표 지향 이동(예: 귀소 경로 적분) 시 조향에 관여하는 것으로 알려진 출력뉴런.",
  },
  {
    match: (t) => t === "PFL3",
    text: "PFL3 — 좌우 비대칭 신호로 회전을 직접 유도하는 것으로 가장 잘 알려진 조향 출력뉴런. Rayshubskiy et al. 2020.",
  },
];

export function curatedFlyDescriptionFor(cellType: string | null): string | null {
  if (!cellType) return null;
  for (const entry of CURATED_TYPE_INFO) {
    if (entry.match(cellType)) return entry.text;
  }
  return null;
}

export function circuitClassDescriptionFor(neuron: Neuron): string | null {
  for (const category of neuron.categories_ko) {
    if (CIRCUIT_CLASS_DESCRIPTION[category]) return CIRCUIT_CLASS_DESCRIPTION[category];
  }
  return null;
}
