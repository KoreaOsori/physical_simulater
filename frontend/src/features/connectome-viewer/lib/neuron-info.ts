import type { Connectome, Neuron } from "@/types/connectome";

/**
 * Bonus one-line Korean function summaries for ~55 especially well-studied
 * C. elegans neuron classes, on top of the real per-neuron data every one of
 * the 302 neurons now carries (`categories_ko` / `description_en`, sourced
 * from WormBase's anatomy ontology — see
 * backend/app/data/sources/SOURCES.md and docs/06-*.md). Keyed by neuron
 * *class* — e.g. "AVA" covers both AVAL and AVAR. Classes without an entry
 * here simply don't get this bonus line; they still show the full sourced
 * category/definition/connectivity data via `summarizeNeuron` below.
 */
const CURATED_CLASS_INFO: Record<string, string> = {
  AVA: "후진 운동을 지휘하는 핵심 명령 인터뉴런. VA/DA 운동뉴런에 강하게 연결되어 후진 시퀀스를 구동합니다.",
  AVB: "전진 운동을 지휘하는 핵심 명령 인터뉴런. VB/DB 운동뉴런에 연결되어 전진 시퀀스를 구동합니다.",
  AVD: "후진 회피 반응에 관여하는 명령 인터뉴런. 전방 접촉 자극을 AVA로 중계합니다.",
  AVE: "후진 운동 회로의 보조 명령 인터뉴런.",
  PVC: "전진 운동을 지휘하는 후방 명령 인터뉴런. 꼬리 접촉 회피 시 전진을 유도합니다.",
  RIM: "운동 상태 전환(전진↔후진)을 조절하는 인터뉴런.",
  RIA: "여러 감각 정보를 통합해 머리 방향 전환(steering)을 조절하는 인터뉴런.",
  RIB: "전진 운동 회로를 조절하는 인터뉴런.",
  RIC: "옥토파민성 인터뉴런으로 각성/이동 상태를 조절합니다.",
  RIF: "행동 상태 전환에 관여하는 인터뉴런.",
  RIG: "감각 통합에 관여하는 인터뉴런.",
  RIH: "인두-신체 신경 연결에 관여하는 인터뉴런.",
  RIS: "수면(lethargus) 상태를 유도하는 인터뉴런.",
  RIP: "인두신경계와 몸신경계를 잇는 유일한 인터뉴런.",
  ALM: "몸 앞쪽 부드러운 접촉을 감지하는 기계감각뉴런. 후진 반응을 유발합니다.",
  AVM: "몸 앞쪽 부드러운 접촉을 감지하는 기계감각뉴런.",
  PLM: "몸 뒤쪽 부드러운 접촉을 감지하는 기계감각뉴런. 전진 가속을 유발합니다.",
  PVM: "몸 뒤쪽 부드러운 접촉을 보조 감지하는 기계감각뉴런.",
  PVD: "강한(harsh) 접촉·냉각을 감지하는 다분지 기계감각뉴런.",
  FLP: "머리의 강한 접촉·온도를 감지하는 기계감각뉴런.",
  ASE: "수용성 염분(소금) 농도를 감지하는 화학감각뉴런. 좌우(ASEL/ASER)가 서로 다른 이온을 감지합니다.",
  ASH: "유해 자극(강한 화학물질, 삼투압 충격, 접촉)을 감지하는 다중모드 회피 감각뉴런.",
  ASI: "먹이 환경·페로몬을 감지해 발달·섭식 행동에 영향을 주는 화학감각뉴런.",
  ASJ: "환경 신호를 감지해 발달(dauer) 결정에 관여하는 화학감각뉴런.",
  ASK: "페로몬·먹이 신호를 감지하는 화학감각뉴런.",
  ASG: "환경 신호 통합에 관여하는 화학감각뉴런.",
  AWA: "휘발성 유인 냄새(먹이 냄새)를 감지하는 후각뉴런.",
  AWB: "휘발성 기피 냄새를 감지하는 후각뉴런.",
  AWC: "휘발성 유인 냄새를 감지하는 후각뉴런. 좌우가 서로 다른 냄새 수용체를 발현합니다.",
  ADF: "세로토닌성 화학감각뉴런으로 섭식·발달 상태에 관여합니다.",
  ADL: "유해 화학물질·페로몬을 감지해 회피를 유도하는 화학감각뉴런.",
  AFD: "온도를 감지하는 주 온도감각뉴런.",
  URX: "체내 산소(O2) 농도를 감지하는 감각뉴런.",
  BAG: "체내 이산화탄소(CO2)·산소 농도를 감지하는 감각뉴런.",
  AQR: "체강액을 통해 산소를 감지하는 감각뉴런.",
  PQR: "체강액을 통해 산소를 감지하는 감각뉴런(꼬리쪽).",
  M1: "인두 운동뉴런 — 인두 근육 수축(펌핑)을 구동합니다.",
  M2L: "인두 운동뉴런 — 인두 근육 수축(펌핑)을 구동합니다.",
  M2R: "인두 운동뉴런 — 인두 근육 수축(펌핑)을 구동합니다.",
  M3L: "인두 운동뉴런 — 인두 재개폐(펌핑 종료)를 구동합니다.",
  M3R: "인두 운동뉴런 — 인두 재개폐(펌핑 종료)를 구동합니다.",
  M4: "인두 연동운동(먹이를 장으로 보내는 수축)을 구동하는 운동뉴런.",
  M5: "인두 운동뉴런.",
  MC: "인두 운동뉴런 — 빠른 펌핑 리듬을 구동합니다.",
  MI: "인두 인터뉴런.",
  I1L: "인두 인터뉴런 — 먹이 감지에 따른 펌핑 속도 조절에 관여.",
  I1R: "인두 인터뉴런 — 먹이 감지에 따른 펌핑 속도 조절에 관여.",
  NSML: "세로토닌성 인두 인터뉴런/신경분비세포 — 먹이 존재 시 펌핑을 촉진합니다.",
  NSMR: "세로토닌성 인두 인터뉴런/신경분비세포 — 먹이 존재 시 펌핑을 촉진합니다.",
  DA: "체벽근을 구동하는 등쪽(dorsal) 후진 운동뉴런.",
  DB: "체벽근을 구동하는 등쪽(dorsal) 전진 운동뉴런.",
  DD: "체벽근 억제성(GABA성) 운동뉴런 — 등/배 교대 수축을 만듭니다.",
  VA: "체벽근을 구동하는 배쪽(ventral) 후진 운동뉴런.",
  VB: "체벽근을 구동하는 배쪽(ventral) 전진 운동뉴런.",
  VC: "외음부 근육과 배쪽 체벽근에 연결되는 운동뉴런 — 산란 행동에 관여.",
  VD: "체벽근 억제성(GABA성) 운동뉴런 — 등/배 교대 수축을 만듭니다.",
  AS: "체벽근을 구동하는 운동뉴런 (후진 회로와 연계).",
  HSN: "세로토닌성 산란(egg-laying) 명령 뉴런 — 외음부 근육 수축을 유도합니다.",
  AVL: "GABA성 배설 명령 뉴런 — DVB와 함께 배설 운동 주기를 구동합니다.",
  DVB: "배설 운동 프로그램의 핵심 운동뉴런 — 장-항문 근육 수축을 구동합니다.",
  RMD: "머리 굽힘(steering)을 담당하는 머리 운동뉴런.",
  SMD: "머리·목 굽힘을 담당하는 운동뉴런 — 방향 전환에 관여.",
  RIV: "머리 방향 전환을 보조하는 운동뉴런.",
  SMB: "몸 전체의 파형 진폭을 조절하는 운동뉴런.",
  RME: "머리 근육을 구동하는 GABA성 운동뉴런.",
  PVR: "후방 인터뉴런.",
  PVT: "전후 신경삭을 잇는 인터뉴런.",
  DVA: "신장 감지(伸張, stretch)에 관여하는 것으로 알려진 인터뉴런.",
  DVC: "후방 인터뉴런.",
  ALA: "수면/각성 상태 조절에 관여하는 인터뉴런.",
  PVW: "후방 인터뉴런.",
  PVN: "후방 인터뉴런.",
  PVP: "전후 신경삭을 잇는 인터뉴런.",
};

function classify(id: string): string[] {
  const noDigits = id.replace(/\d+$/, "");
  const noDigitsNoLR = noDigits.replace(/[LR]$/, "");
  return [id, noDigits, noDigitsNoLR];
}

export function curatedDescriptionFor(neuronId: string): string | null {
  for (const key of classify(neuronId)) {
    if (CURATED_CLASS_INFO[key]) return CURATED_CLASS_INFO[key];
  }
  return null;
}

const TYPE_LABEL: Record<Neuron["type"], string> = {
  sensory: "감각뉴런",
  inter: "중간뉴런",
  motor: "운동뉴런",
  unknown: "역할 미확인",
};

const NT_LABEL: Record<string, string> = {
  acetylcholine: "아세틸콜린",
  gaba: "GABA",
  glutamate: "글루탐산",
  dopamine: "도파민",
  serotonin: "세로토닌",
  octopamine: "옥토파민",
  tyramine: "티라민",
  electrical: "전기 시냅스",
  unknown: "미확인",
};

export interface NeuronSummary {
  id: string;
  typeLabel: string;
  ntLabel: string;
  outDegree: number;
  inDegree: number;
  topPartners: string[];
  /** Korean category tags from WormBase's anatomy ontology (real, sourced) —
   * the primary "what is this neuron" content, covering all 302 neurons
   * (only CANL/CANR, which have no curated ontology categories, come back empty). */
  categoriesKo: string[];
  /** WormBase anatomy ontology definition, English, quoted verbatim — kept
   * untranslated to avoid mistranslating a scientific source. */
  descriptionEn: string | null;
  wormatlasUrl: string | null;
  /** Hand-authored one-line Korean function summary for ~55 especially
   * well-known classes — a bonus on top of the sourced data above, not a
   * replacement for it (see docs/06-*.md for why not all 302 are covered
   * this way). */
  curated: string | null;
}

/** Everything in this summary comes from the loaded connectome (real,
 * sourced data — see backend/app/data/sources/SOURCES.md) except `curated`,
 * the hand-authored bonus note above. */
export function summarizeNeuron(neuron: Neuron, connectome: Connectome): NeuronSummary {
  const outgoing = connectome.synapses.filter((s) => s.pre === neuron.id);
  const incoming = connectome.synapses.filter((s) => s.post === neuron.id);
  const partnerCounts = new Map<string, number>();
  for (const s of outgoing) partnerCounts.set(s.post, (partnerCounts.get(s.post) ?? 0) + 1);
  const topPartners = [...partnerCounts.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 4)
    .map(([id]) => id);

  return {
    id: neuron.id,
    typeLabel: TYPE_LABEL[neuron.type],
    ntLabel: NT_LABEL[neuron.neurotransmitter] ?? neuron.neurotransmitter,
    outDegree: outgoing.length,
    inDegree: incoming.length,
    topPartners,
    categoriesKo: neuron.categories_ko,
    descriptionEn: neuron.description_en,
    wormatlasUrl: neuron.wormatlas_url,
    curated: curatedDescriptionFor(neuron.id),
  };
}
