"""Real, per-region anatomical labels for the macro connectome's Vis/Limbic
parcels — Schaefer atlas region names at 400-parcel resolution are just
"Vis_1".."Vis_31" (no finer real anatomical subdivision name at this
resolution, unlike Limbic's own OFC/TempPole split), so every Vis tooltip
showed the identical generic boilerplate. This looks up each region's real
MNI centroid in the AAL (Automated Anatomical Labeling) atlas to find which
named anatomical structure it actually sits in/near.

Source: AAL (Tzourio-Mazoyer et al. 2002, NeuroImage 15:273), vendored via
FieldTrip toolbox's redistribution (`app/data/sources/human/aal/`,
`ROI_MNI_V4.nii` + `ROI_MNI_V4.txt`), MNI152 2mm space — same coordinate
convention as the Schaefer region centroids.

Honesty caveat (see SOURCES.md): this is a coordinate LOOKUP, not a claim
that a Schaefer parcel and an AAL region are the same thing — a Schaefer
parcel's centroid sitting inside "Lingual_L" means "this parcel's central
point is closest to/inside the real Lingual gyrus," not "this parcel IS the
lingual gyrus" (parcel boundaries and AAL region boundaries don't align).
"""

from __future__ import annotations

import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

import nibabel as nib
import numpy as np

from app.data.human_lobes import LOBE_OTHER, lobe_for_anatomical_label

AAL_DIR = Path(__file__).resolve().parent.parent / "app" / "data" / "sources" / "human" / "aal"
AAL_NII_PATH = AAL_DIR / "ROI_MNI_V4.nii"
AAL_LABELS_PATH = AAL_DIR / "ROI_MNI_V4.txt"

# Short, general-neuroanatomy-textbook functional notes per AAL base name
# (hemisphere suffix _L/_R stripped) — well-established facts (e.g. Calcarine
# = primary visual cortex), not this project's own claims. Deliberately
# short; not a substitute for a real neuroanatomy reference.
_DESCRIPTIONS: dict[str, str] = {
    "Calcarine": "일차시각피질(V1)이 위치하는 곳 — 망막에서 온 시각 신호가 대뇌피질에 처음 도달하는 부위.",
    "Cuneus": "쐐기소엽 — 일차시각피질과 인접한 상부 시각피질.",
    "Lingual": "설상이랑 — 시각연합피질, 색·형태 처리에 관여.",
    "Fusiform": "방추이랑 — 고차 시각처리(얼굴·사물 인식)에 관여하는 측두-후두 경계 영역.",
    "Occipital_Sup": "후두엽 상이랑 — 시각연합피질.",
    "Occipital_Mid": "후두엽 중간이랑 — 시각연합피질.",
    "Occipital_Inf": "후두엽 하이랑 — 시각연합피질, 측두엽과 경계.",
    "ParaHippocampal": "해마곁이랑 — 장면·공간 기억과 시각 정보를 연결.",
    "Parietal_Sup": "상두정소엽 — 공간 주의·시각-운동 통합.",
    "Temporal_Inf": "하측두이랑 — 고차 시각처리(사물 인식)에 관여.",
    "Temporal_Mid": "중간측두이랑 — 고차 시각·의미 처리.",
    "Frontal_Sup_Orb": "안와전두피질(상부) — 의사결정·보상가치 평가.",
    "Frontal_Mid_Orb": "안와전두피질(중간) — 의사결정·보상가치 평가.",
    "Frontal_Inf_Orb": "안와전두피질(하부) — 의사결정·정서 조절.",
    "Frontal_Med_Orb": "내측 안와전두피질 — 보상·정서가치 평가.",
    "Rectus": "직회 — 안와전두피질의 일부, 정서·보상 처리.",
    "Temporal_Pole_Sup": "상측두극 — 사회적 인지·의미기억, 변연계와 연결.",
    "Temporal_Pole_Mid": "중간측두극 — 의미기억·개념 표상, 변연계와 연결.",
    # SomMot, DorsAttn, SalVentAttn, Cont, Default 네트워크 확장(6차 패스)에서 추가.
    "Postcentral": "중심뒤이랑 — 일차체성감각피질(S1), 촉각 등 몸감각이 대뇌피질에 처음 도달하는 곳.",
    "Precentral": "중심앞이랑 — 일차운동피질(M1), 수의운동 명령의 최종 출력.",
    "Paracentral_Lobule": "방정중소엽 — 하지의 체성감각·운동을 담당.",
    "Rolandic_Oper": "롤란도판개 — 일차체성감각/운동피질과 인접, 구강·안면 운동에 관여.",
    "Supp_Motor_Area": "보조운동영역 — 운동 계획·순서화.",
    "Heschl": "헤슬이랑 — 일차청각피질.",
    "Temporal_Sup": "위측두이랑 — 청각연합피질 포함, 언어·사회적 소리 처리.",
    "SupraMarginal": "모서리위이랑 — 언어 처리, 촉각-공간 정보 통합.",
    "Parietal_Inf": "하두정소엽 — 공간 주의·감각 통합.",
    "Angular": "각이랑 — 디폴트모드 네트워크 핵심 허브, 의미 처리·주의 전환.",
    "Precuneus": "쐐기앞소엽 — 디폴트모드 네트워크 핵심부위, 자기참조적 사고·에피소드 기억 인출.",
    "Frontal_Sup": "위이마이랑 — 배외측 전전두피질, 집행기능·작업기억.",
    "Frontal_Mid": "중간이마이랑 — 배외측 전전두피질, 작업기억·집행기능·의사결정.",
    "Frontal_Sup_Medial": "내측 위이마이랑 — 디폴트모드 네트워크와 집행기능 네트워크의 경계 영역.",
    "Frontal_Inf_Tri": "아래이마이랑 삼각부 — 브로카 영역의 일부, 언어 산출에 관여.",
    "Frontal_Inf_Oper": "아래이마이랑 판개부 — 브로카 영역의 일부, 언어 산출에 관여.",
    "Insula": "뇌섬엽 — 내수용감각(신체 내부 상태 인지)·정서·현출성 네트워크의 핵심.",
    "Cingulum_Ant": "앞대상피질 — 정서 조절·갈등 모니터링, 현출성 네트워크에 관여.",
    "Cingulum_Mid": "중간대상피질 — 인지 통제·갈등 모니터링.",
    "Cingulum_Post": "뒤대상피질 — 디폴트모드 네트워크의 핵심 허브, 자기참조 사고·기억 인출.",
}


# Real, well-established lesion-symptom associations (classic clinical
# neurology — e.g. Wernicke's/Broca's aphasia, Phineas Gage's orbitofrontal
# injury, Gerstmann syndrome) keyed by the AAL base name(s) whose damage is
# classically associated with each syndrome. This is honest textbook-level
# lesion mapping, not this project's own diagnosis or claim that damage to
# exactly this Schaefer parcel causes exactly this syndrome — see the
# `caveat` text surfaced with every entry.
#
# `category`:
#   "focal"   — a classic single-lesion syndrome, one small/specific region
#               (or a bilateral pair) whose damage is directly implicated.
#   "complex" — a real condition with well-documented involvement across
#               MANY regions/networks and a genuinely multifactorial cause
#               (genetic, developmental, neurochemical, environmental) —
#               the region list shows "regions consistently implicated in
#               the literature," not "the cause," and that distinction is
#               surfaced separately in the UI rather than mixed into the
#               same list as focal lesion syndromes.
_DISORDER_CAVEAT = (
    "실제 원인·경과는 이보다 훨씬 복잡하고 다양할 수 있음 — "
    "고전적인 병변-증상 대응 사례를 참고한 교육용 설명."
)
_COMPLEX_CAVEAT = (
    "단일 부위 손상으로 생기는 병이 아니라, 유전·발달·신경전달물질·환경 등 "
    "여러 요인이 겹쳐 나타나는 복합질환이다 — 아래 부위들은 문헌에서 "
    "반복적으로 이상 소견이 보고된 곳일 뿐, \"이 부위가 원인이다\"라는 뜻이 아니다."
)

DISORDERS: list[dict[str, object]] = [
    # --- 국소 병변 증후군 (focal) — 특정 소수 부위 손상과 직접 연결되는 고전적 사례 ---
    {
        "name": "대뇌색맹 (Cerebral Achromatopsia)",
        "category": "focal",
        "description": f"색채를 처리하는 시각연합피질(V4 부근)이 손상되면 형태·움직임 지각은 보존된 채 색채 인식만 상실될 수 있다. {_DISORDER_CAVEAT}",
        "labels": ["Lingual", "Fusiform"],
    },
    {
        "name": "피질맹 (Cortical Blindness)",
        "category": "focal",
        "description": f"일차시각피질(V1)이 양측으로 손상되면 눈 자체는 멀쩡해도 시야 전체를 보지 못할 수 있다(동공반사는 정상). {_DISORDER_CAVEAT}",
        "labels": ["Calcarine"],
    },
    {
        "name": "안면실인증 (Prosopagnosia)",
        "category": "focal",
        "description": f"방추이랑(방추형 얼굴 영역)이 손상되면 다른 사물 인식은 보존된 채 얼굴만 구별하지 못할 수 있다. {_DISORDER_CAVEAT}",
        "labels": ["Fusiform"],
    },
    {
        "name": "운동맹 (Akinetopsia)",
        "category": "focal",
        "description": f"측두-후두 경계(MT/V5 부근)가 손상되면 물체는 보이지만 움직임 자체를 지각하지 못하는 매우 드문 증상이 보고된 바 있다. {_DISORDER_CAVEAT}",
        "labels": ["Occipital_Mid", "Occipital_Sup"],
    },
    {
        "name": "반신마비 (Hemiplegia)",
        "category": "focal",
        "description": f"일차운동피질(M1)이 손상되면 반대쪽 신체가 마비될 수 있다 — 손상 위치가 운동 호문쿨루스의 어느 부위냐에 따라 마비되는 신체 부위가 달라진다. {_DISORDER_CAVEAT}",
        "labels": ["Precentral"],
    },
    {
        "name": "반신감각소실 (Hemisensory Loss)",
        "category": "focal",
        "description": f"일차체성감각피질(S1)이 손상되면 반대쪽 신체의 촉각·통증 감각이 소실될 수 있다. {_DISORDER_CAVEAT}",
        "labels": ["Postcentral"],
    },
    {
        "name": "베르니케 실어증 (Wernicke's Aphasia)",
        "category": "focal",
        "description": f"위측두이랑 후방(베르니케 영역)이 손상되면 말은 유창하지만 의미가 통하지 않고, 언어 이해에도 장애가 생길 수 있다. {_DISORDER_CAVEAT}",
        "labels": ["Temporal_Sup"],
    },
    {
        "name": "청각실인증 (Auditory Agnosia)",
        "category": "focal",
        "description": f"일차청각피질(헤슬이랑)이 손상되면 소리는 들리지만 그 의미를 해석하지 못할 수 있다. {_DISORDER_CAVEAT}",
        "labels": ["Heschl"],
    },
    {
        "name": "브로카 실어증 (Broca's Aphasia)",
        "category": "focal",
        "description": f"아래이마이랑(브로카 영역)이 손상되면 언어 이해는 비교적 보존되지만 말을 산출하기 어려워질 수 있다(어눌하고 힘겨운 발화). {_DISORDER_CAVEAT}",
        "labels": ["Frontal_Inf_Tri", "Frontal_Inf_Oper"],
    },
    {
        "name": "집행기능장애 (Executive Dysfunction)",
        "category": "focal",
        "description": f"배외측 전전두피질이 손상되면 계획 수립·작업기억·충동 억제 등 집행기능이 저하될 수 있다. {_DISORDER_CAVEAT}",
        "labels": ["Frontal_Sup", "Frontal_Mid"],
    },
    {
        "name": "안와전두 증후군 (Orbitofrontal Syndrome)",
        "category": "focal",
        "description": f"안와전두피질이 손상되면 판단력·충동 조절이 저하되고 성격이 변할 수 있다 — 1848년 철도 사고로 이 부위를 다친 피니어스 게이지(Phineas Gage) 사례가 가장 유명하다. {_DISORDER_CAVEAT}",
        "labels": ["Frontal_Sup_Orb", "Frontal_Mid_Orb", "Frontal_Inf_Orb", "Frontal_Med_Orb", "Rectus"],
    },
    {
        "name": "의미치매 (Semantic Dementia)",
        "category": "focal",
        "description": f"측두극이 위축되면(전측두엽 치매의 한 유형) 단어와 사물의 의미 지식이 점차 상실될 수 있다. {_DISORDER_CAVEAT}",
        "labels": ["Temporal_Pole_Sup", "Temporal_Pole_Mid"],
    },
    {
        "name": "전행성 기억상실증 (Anterograde Amnesia)",
        "category": "focal",
        "description": f"해마곁이랑(해마 주변 구조)이 손상되면 새로운 사건을 장기기억으로 저장하는 능력이 저하될 수 있다. {_DISORDER_CAVEAT}",
        "labels": ["ParaHippocampal"],
    },
    {
        "name": "게르스트만 증후군 (Gerstmann Syndrome)",
        "category": "focal",
        "description": f"각이랑이 손상되면 계산불능·쓰기언어장애·손가락인식불능·좌우혼동 네 가지 증상이 함께 나타날 수 있다. {_DISORDER_CAVEAT}",
        "labels": ["Angular"],
    },
    {
        "name": "편측무시 (Hemispatial Neglect)",
        "category": "focal",
        "description": f"두정엽(주로 우반구)이 손상되면 반대쪽 공간 자체를 인지하지 못하는 증상이 나타날 수 있다. {_DISORDER_CAVEAT}",
        "labels": ["Parietal_Sup", "Parietal_Inf", "SupraMarginal"],
    },
    # --- 아래 9개는 v5(docs/33)에서 추가 — 기존 20개가 네트워크/엽별로 매우
    # 고르지 못하게 분포된 것을 보완하려고 실제 문헌으로 검증 후 추가했다
    # (특히 SalVentAttn 네트워크가 0개였던 것, 후두엽이 3개뿐이었던 것). ---
    {
        "name": "발린트 증후군 (Balint's Syndrome)",
        "category": "focal",
        "description": f"양측 후두정엽이 손상되면 동시실인증(한 번에 한 물체만 지각)·시각운동실조(눈으로 본 곳에 손을 뻗지 못함)·안구운동실행증(시선을 의도대로 옮기지 못함) 세 증상이 함께 나타날 수 있다. {_DISORDER_CAVEAT}",
        "labels": ["Parietal_Sup", "Parietal_Inf"],
    },
    {
        "name": "미각상실증 (Ageusia)",
        "category": "focal",
        "description": f"뇌섬엽(일차미각피질)이 손상되면 미각을 느끼지 못하거나 왜곡될 수 있다 — 실제로는 인접한 이마엽 판개부도 함께 관여하는 것으로 알려져 있으나 이 데이터셋은 뇌섬엽 라벨만 사용한다. {_DISORDER_CAVEAT}",
        "labels": ["Insula"],
    },
    {
        "name": "카그라스 증후군 (Capgras Syndrome)",
        "category": "focal",
        "description": f"방추이랑(얼굴 인식)과 정서 반응 경로 사이가 단절되면 가까운 사람이 똑같이 생긴 가짜로 바뀌었다고 믿는 망상이 나타날 수 있다(우반구 손상과 자주 연관) — 정확한 기전은 아직 논쟁적이다. {_DISORDER_CAVEAT}",
        "labels": ["Fusiform"],
    },
    {
        "name": "복측 동시실인증 (Ventral Simultanagnosia)",
        "category": "focal",
        "description": f"좌측 후두-측두 경계가 손상되면(발린트 증후군의 배측형과 달리 시각운동실조·안구운동실행증 없이) 여러 물체를 동시에 지각하지 못하고 한 번에 하나씩만 읽거나 볼 수 있다. {_DISORDER_CAVEAT}",
        "labels": ["Occipital_Inf", "Temporal_Inf"],
    },
    {
        "name": "무동성 무언증 (Akinetic Mutism)",
        "category": "focal",
        "description": f"양측 앞대상피질(및 보조운동영역)이 손상되면 각성 상태이고 근력도 정상이지만 스스로 움직이거나 말하려는 의지 자체가 사라질 수 있다. {_DISORDER_CAVEAT}",
        "labels": ["Cingulum_Ant", "Supp_Motor_Area"],
    },
    {
        "name": "동측반맹 (Homonymous Hemianopia)",
        "category": "focal",
        "description": f"한쪽 일차시각피질(V1)이 손상되면 양쪽 눈 모두에서 반대쪽 시야 절반을 보지 못할 수 있다 — 실제로는 한쪽만 손상돼도 나타나지만, 이 데이터셋은 좌우 반구를 구분해 표시하지 않아 양측 Calcarine 영역이 함께 표시된다. {_DISORDER_CAVEAT}",
        "labels": ["Calcarine"],
    },
    {
        "name": "안톤 증후군 (Anton Syndrome)",
        "category": "focal",
        "description": f"양측 일차시각피질이 손상되면 실제로는 앞을 못 보면서도 본인은 잘 보인다고 부인하고 없는 장면을 지어내 말할 수 있다 — 같은 부위 손상인 피질맹과 달리 스스로 실명을 인지하지 못하는 것이 핵심 특징이다. {_DISORDER_CAVEAT}",
        "labels": ["Calcarine"],
    },
    {
        "name": "샤를 보네 증후군 (Charles Bonnet Syndrome)",
        "category": "focal",
        "description": f"설상이랑·방추이랑 등 시각연합피질 자체는 멀쩡한데 그 입력원(눈·시신경 등)이 손상되면, 이 부위들이 스스로 과활성되며 실제로 없는 사람·사물이 보이는 생생한 환시가 나타날 수 있다 — 이 부위가 '손상'된 게 아니라 입력이 끊겨 과활성되는 것이라 다른 항목들과 인과 구조가 다르다. {_DISORDER_CAVEAT}",
        "labels": ["Lingual", "Fusiform"],
    },
    {
        "name": "클루버-부시 증후군 (Klüver-Bucy Syndrome)",
        "category": "focal",
        "description": f"양측 측두극(및 인접 내측두엽)이 손상되면 과도한 구강탐색행동·과잉성욕·온순함·시각실인증이 함께 나타날 수 있다 — 1939년 원숭이 실험에서 처음 보고됐고 이후 사람에게서도 실제로 확인됐다. {_DISORDER_CAVEAT}",
        "labels": ["Temporal_Pole_Sup", "Temporal_Pole_Mid"],
    },
    {
        "name": "반신마비 무인지증 (Anosognosia for Hemiplegia)",
        "category": "focal",
        # 다른 focal 항목과 달리 단일/소수 인접 부위가 아니라 여러 영역에
        # 걸친 복합 손상이 전형적으로 보고된다(Vocat et al. 2010) — 그래도
        # "complex" 카테고리(유전·발달·신경전달물질 등 다인성 원인)로
        # 분류하면 실제로는 뇌졸중 등 국소 병변이 원인이라는 사실을 왜곡하게
        # 되므로, category는 focal로 유지하고 이 차이를 설명에 직접 명시한다.
        "description": f"우반구 뇌섬엽·모서리위이랑·중간이마이랑 등 여러 영역에 걸친 손상이 함께 나타날 때 보고되는 경우가 많다 — 반대쪽 신체가 실제로 마비됐는데도 본인은 마비 사실 자체를 인지하지 못하거나 부인할 수 있다(단일 부위가 아니라 여러 부위의 복합 손상이 전형적이라는 점에서 다른 국소 증후군과 차이가 있다). {_DISORDER_CAVEAT}",
        "labels": ["Insula", "SupraMarginal", "Parietal_Inf", "Frontal_Mid"],
    },
    # --- 복합·다발성 질환 (complex) — 여러 네트워크에 걸쳐 이상이 보고되고
    # 원인 자체가 다인성인 질환. 국소 병변 증후군과 섞이지 않도록 구분. ---
    {
        "name": "알츠하이머병 (Alzheimer's Disease)",
        "category": "complex",
        "description": f"해마곁이랑·측두엽·두정엽·뒤대상피질/쐐기앞소엽(디폴트모드 네트워크 핵심부)에 걸쳐 위축·대사저하가 진행성으로 나타난다 — 특히 뒤대상피질/쐐기앞소엽은 초기에 가장 먼저 이상이 관찰되는 부위로 잘 알려져 있다. {_COMPLEX_CAVEAT}",
        "labels": ["ParaHippocampal", "Temporal_Sup", "Temporal_Inf", "Parietal_Sup", "Parietal_Inf", "Precuneus", "Cingulum_Post"],
    },
    {
        "name": "조현병 (Schizophrenia)",
        "category": "complex",
        "description": f"위측두이랑·배외측 전전두피질·앞대상피질 등 여러 영역에 걸쳐 회백질 부피 감소와 연결성 이상이 반복적으로 보고된다(\"연결이상 가설\"). {_COMPLEX_CAVEAT}",
        "labels": ["Temporal_Sup", "Frontal_Sup", "Frontal_Mid", "Cingulum_Ant"],
    },
    {
        "name": "주요우울장애 (Major Depressive Disorder)",
        "category": "complex",
        "description": f"앞대상피질·배외측 전전두피질·뇌섬엽의 활동/연결성 이상이 정서 조절 곤란과 관련된 것으로 반복 보고된다. {_COMPLEX_CAVEAT}",
        "labels": ["Cingulum_Ant", "Frontal_Sup", "Frontal_Mid", "Insula"],
    },
    {
        "name": "자폐스펙트럼장애 (Autism Spectrum Disorder)",
        "category": "complex",
        "description": f"방추이랑(얼굴 처리)·측두극·안와전두피질 등 사회인지 관련 영역의 발달·연결성 차이가 보고된다. {_COMPLEX_CAVEAT}",
        "labels": ["Fusiform", "Temporal_Pole_Sup", "Temporal_Pole_Mid", "Frontal_Inf_Orb", "Frontal_Sup_Orb"],
    },
    {
        "name": "외상후 스트레스장애 (PTSD)",
        "category": "complex",
        "description": f"앞대상피질·뇌섬엽·해마곁이랑을 포함하는 공포·정서 조절 회로의 과활성/조절이상이 보고된다. {_COMPLEX_CAVEAT}",
        "labels": ["Cingulum_Ant", "Insula", "ParaHippocampal"],
    },
    {
        "name": "강박장애 (Obsessive-Compulsive Disorder)",
        "category": "complex",
        "description": f"안와전두피질·앞대상피질의 과활성이 반복적으로 보고되며(안와전두-선조체 회로 가설), 특정 생각(강박사고)과 반복 행동(강박행동)에서 벗어나기 어려운 상태로 나타난다. {_COMPLEX_CAVEAT}",
        "labels": ["Frontal_Sup_Orb", "Frontal_Mid_Orb", "Frontal_Inf_Orb", "Frontal_Med_Orb", "Cingulum_Ant"],
    },
    {
        "name": "이인증-비현실감 장애 (Depersonalization-Derealization Disorder)",
        "category": "complex",
        "description": f"뇌섬엽·앞대상피질(내수용감각·정서 처리 핵심부)의 반응성 저하가 보고되며, 자기 자신이나 주변 세계가 낯설고 비현실적으로 느껴지는 상태가 지속될 수 있다. {_COMPLEX_CAVEAT}",
        "labels": ["Insula", "Cingulum_Ant"],
    },
]


def resolve_disorders(regions: list[dict]) -> list[dict]:
    """Groups the already-built region list by real anatomical_label (base
    name), then resolves each DISORDERS entry's implicated labels to the
    actual region ids present in THIS dataset — so `region_ids` only ever
    names regions that really exist and really carry that label, never a
    guess.

    For "focal" entries, also picks a `primary_network`: whichever real
    Yeo-7 network the majority of its resolved regions actually belong to
    (a plain vote over real network membership, not a guess) — lets the
    frontend group a focal syndrome under the one network it mostly lives
    in. "complex" entries get `primary_network=None`: by definition they're
    spread across many networks with no honest single-network home, so the
    frontend always shows them in a separate "공통" section instead of
    picking one network to hide them under.

    `primary_lobe` (docs/33) works exactly the same way, one level down —
    same majority-vote logic, over the real AAL-derived classical 4-lobe
    mapping (human_lobes.py) instead of the Yeo-7 network. Also left `None`
    for "complex" entries for the identical honesty reason, and also `None`
    for any focal entry whose matched regions all fall outside the 4
    classical lobes (e.g. Insula/Cingulum-only entries like Ageusia) —
    never forced into a lobe bucket it doesn't really belong to."""
    region_ids_by_base: dict[str, list[str]] = {}
    network_by_id: dict[str, str] = {}
    anatomical_label_by_id: dict[str, str] = {}
    for r in regions:
        network_by_id[r["id"]] = r["network"]
        label = r.get("anatomical_label")
        if not label:
            continue
        anatomical_label_by_id[r["id"]] = label
        region_ids_by_base.setdefault(_base_name(label), []).append(r["id"])

    resolved = []
    for disorder in DISORDERS:
        region_ids: list[str] = []
        for label in disorder["labels"]:
            region_ids.extend(region_ids_by_base.get(label, []))
        if not region_ids:
            continue  # honestly omit a disorder whose labels matched nothing in this dataset

        primary_network = None
        primary_lobe = None
        if disorder["category"] == "focal":
            network_votes: dict[str, int] = {}
            lobe_votes: dict[str, int] = {}
            for rid in region_ids:
                network_votes[network_by_id[rid]] = network_votes.get(network_by_id[rid], 0) + 1
                # LOBE_OTHER (Insula/Cingulum/ParaHippocampal -- real AAL
                # structures, but not part of the classical 4 lobes) is
                # deliberately excluded from the vote, same as a missing
                # label -- `primary_lobe` only ever names one of the 4 real
                # lobes or None, never "other" (the frontend's 4-lobe UI has
                # no slot for a 5th bucket, see docs/33).
                lobe = lobe_for_anatomical_label(anatomical_label_by_id.get(rid))
                if lobe and lobe != LOBE_OTHER:
                    lobe_votes[lobe] = lobe_votes.get(lobe, 0) + 1
            primary_network = max(network_votes, key=lambda n: network_votes[n])
            if lobe_votes:
                primary_lobe = max(lobe_votes, key=lambda l: lobe_votes[l])

        resolved.append(
            {
                "name": disorder["name"],
                "category": disorder["category"],
                "primary_network": primary_network,
                "primary_lobe": primary_lobe,
                "description": disorder["description"],
                "anatomical_labels": disorder["labels"],
                "region_ids": region_ids,
            }
        )
    return resolved


def _base_name(aal_name: str) -> str:
    """"Lingual_L" -> "Lingual" for the description lookup."""
    for suffix in ("_L", "_R"):
        if aal_name.endswith(suffix):
            return aal_name[: -len(suffix)]
    return aal_name


class AalLookup:
    def __init__(self) -> None:
        img = nib.load(AAL_NII_PATH)
        self._data = np.asarray(img.dataobj)
        self._inv_affine = np.linalg.inv(img.affine)
        self._labels: dict[int, str] = {}
        with AAL_LABELS_PATH.open(encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split("\t")
                if len(parts) == 3:
                    self._labels[int(parts[2])] = parts[1]

    def _label_at_voxel(self, vx: int, vy: int, vz: int) -> str | None:
        shape = self._data.shape
        if not (0 <= vx < shape[0] and 0 <= vy < shape[1] and 0 <= vz < shape[2]):
            return None
        value = int(self._data[vx, vy, vz])
        return self._labels.get(value) if value != 0 else None

    def lookup(self, r: float, a: float, s: float, fallback_radius: int = 3) -> tuple[str, str] | None:
        """Real AAL anatomical label + short functional note for an MNI
        coordinate, or None if no AAL-labeled tissue is found within
        `fallback_radius` voxels (background/CSF/outside-atlas point) —
        honestly left unlabeled rather than guessing."""
        voxel = self._inv_affine @ np.array([r, a, s, 1.0])
        vx, vy, vz = (int(round(c)) for c in voxel[:3])

        direct = self._label_at_voxel(vx, vy, vz)
        name = direct
        if name is None:
            best_dist = None
            for dx in range(-fallback_radius, fallback_radius + 1):
                for dy in range(-fallback_radius, fallback_radius + 1):
                    for dz in range(-fallback_radius, fallback_radius + 1):
                        candidate = self._label_at_voxel(vx + dx, vy + dy, vz + dz)
                        if candidate is None:
                            continue
                        dist = dx * dx + dy * dy + dz * dz
                        if best_dist is None or dist < best_dist:
                            best_dist = dist
                            name = candidate
        if name is None:
            return None
        description = _DESCRIPTIONS.get(_base_name(name), "")
        return name, description
