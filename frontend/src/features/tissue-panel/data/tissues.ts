export interface Tissue {
  id: string;
  label: string;
  detail: string;
  description: string;
  color: string;
  planned?: boolean;
}

export const tissues: Tissue[] = [
  {
    id: "neurons",
    label: "신경계",
    detail: "302개 뉴런 · 시냅스 연결",
    description:
      "감각·운동·중간뉴런으로 구성된 302개 뉴런 네트워크입니다. 약 6,900개의 화학적·전기적 시냅스 연결을 추적합니다. 뉴런의 3D 위치는 OpenWorm의 EM(전자현미경) 재구성 데이터에서 가져온 실제 세포체 좌표입니다.",
    color: "#baff71",
  },
  {
    id: "muscle",
    label: "체벽 근육",
    detail: "95개 근육 세포 · 수축 파형",
    description: "등쪽·배쪽 각 2줄씩 총 4열의 체벽근육입니다. 신경 신호에 따라 교대로 수축하며 물결 운동을 만듭니다.",
    color: "#ff9c73",
  },
  {
    id: "intestine",
    label: "장",
    detail: "20개 세포 · 섭식·배설",
    description: "입-인두-장-항문으로 이어지는 소화관입니다. 배설 리듬은 약 45~50초 주기로 조절됩니다.",
    color: "#e8c86d",
    planned: true,
  },
  {
    id: "epidermis",
    label: "상피 · 큐티클",
    detail: "외피 구조 · 감각 입력",
    description: "콜라겐 기반 큐티클층이 기계적 보호와 촉각·화학 감각 뉴런의 외부 자극 감지를 돕습니다.",
    color: "#75cce9",
    planned: true,
  },
  {
    id: "gonad",
    label: "생식선",
    detail: "생식계 · 발생 추적",
    description: "자웅동체 개체에서 정자와 난자를 모두 생성하는 생식소 구조로, 발생 단계 추적 연구에 활용됩니다.",
    color: "#da9bf0",
    planned: true,
  },
];
