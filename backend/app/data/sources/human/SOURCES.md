# 인간(Human) 데이터 출처 및 한계

이 프로젝트의 다른 종(C. elegans, Drosophila)과 동일한 원칙: 실제 공개 데이터만
사용하고, 계산된/근사된 값은 "측정된 값이 아님"을 명시한다. 다만 인간 데이터는
근본적으로 다른 성격을 갖는다는 점을 먼저 밝힌다 — **인간 전체 뇌의 "뉴런 단위
커넥톰"은 세계 어디에도 존재하지 않는다** (860억 뉴런 전체를 EM으로 재구성하는
것은 현재 기술로 불가능). 그래서 이 프로젝트는 실재하는 두 가지 서로 다른
스케일의 데이터를 각각 정직하게 별도로 제공한다 — 하나를 다른 하나인 것처럼
섞지 않는다.

## 1. 거시 커넥톰 — 시각(Vision) 네트워크

**Schaefer 400-parcel, 7-network 파셀레이션** (Schaefer et al. 2018,
*Cerebral Cortex*) + **HCP 기반 그룹 합의 구조 연결성 행렬** (Liu, Shafiei,
Baillet, Mišić 2023, *NeuroImage*, "MEG-SC/FC" 연구 부속 데이터, 33명 HCP
피험자의 확산 MRI 트랙토그래피 합의).

- 원본: `github.com/netneurolab/liu_meg-scfc` (`sc_cons_400_nosubc.npy`, 공개,
  로그인 불필요) + `github.com/ThomasYeoLab/CBIG`
  (`Schaefer2018_400Parcels_7Networks_order_FSLMNI152_1mm.Centroid_RAS.csv`,
  공개, 로그인 불필요).
- 400개 영역 중 이름에 `_Vis_`가 포함된 **61개 시각 관련 영역**만 필터링,
  MNI 좌표계(R/A/S, mm)의 실제 무게중심 좌표를 그대로 사용.
- 연결성 행렬은 **이진(binary) 합의 행렬**이다 — 개별 시냅스도, 가중 스트림라인
  수도 아니고 "33명 피험자 그룹에서 거리보정 후 합의된 연결 유무(0/1)"다.
  시각 영역 간 실제 연결 **465개**를 그대로 벤더링(`schaefer_vis_edges.csv`).
- **한계**: 확산 MRI 트랙토그래피는 실제 축삭 경로가 아니라 물 분자 확산
  방향을 통계적으로 추정한 것이다(방향 모호성, 거짓양성/거짓음성 알려진
  문제). "연결됨"은 "어떤 신경 경로로건 통계적으로 연관됨"을 뜻하지, 웜/초파리
  데이터처럼 실제 축삭 하나하나를 추적해 확인한 시냅스가 아니다.

### 1-1. 2차 패스 추가 — Limbic 네트워크

1차 패스는 Vis(시각) 네트워크 61개 영역만 다뤘다. 2차 패스에서 같은 Schaefer
400-parcel/7-network 원본에서 **Limbic 네트워크 26개 영역**(좌우 OFC 11개 +
TempPole 15개)과 그 사이 실제 합의 연결 **108개**를 추가로 벤더링했다
(`schaefer_limbic_regions.csv`, `schaefer_limbic_edges.csv`).

- 원본은 Vis와 동일한 두 저장소지만, 1차 패스에서는 Vis로 미리 필터링된
  서브셋 CSV만 남기고 원본 400x400 행렬/400개 센트로이드 전체는 보관하지
  않았다 — 2차 패스에서 다시 내려받아(`Schaefer2018_400Parcels_7Networks_order_
  FSLMNI152_1mm.Centroid_RAS.csv`, `sc_cons_400_nosubc.npy`,
  `Schaefer2018_400Parcels_7Networks.npy`) Limbic 라벨(7Networks 순서상 정수
  라벨 4번, `Vis`~`Default` 7개 네트워크와 이름으로 교차검증 완료)에 해당하는
  행만 다시 추출했다. `roi_label`은 이 400개 전체 파셀레이션의 전역 인덱스
  (1~400)이며, Vis/Limbic 서브셋 CSV 안에서도 그대로 유지된다 — 두 네트워크를
  같은 장면에 합쳐도 라벨 충돌이 없다.
- **Limbic을 고른 이유**: 이 네트워크의 TempPole(측두극) 하위 영역이 Schaefer
  7-network 중 H01 미시 샘플의 실제 채취 부위(측두엽)와 해부학적으로 가장
  가까운 대분류다. 다만 **정합된 좌표로 연결한 것은 아니다** — H01은 MNI
  공간에 등록되지 않았으므로, `human_macro_connectome.json`의
  `anatomy.h01_region_hint`는 TempPole 파셀들의 실제 MNI 무게중심일 뿐,
  H01 샘플 좌표 자체가 아니다(정직하게 "인접 부위 안내"로만 표기).

### 1-2. 6차 패스 추가 — 나머지 5개 Yeo-7 네트워크 (SomMot·DorsAttn·SalVentAttn·Cont·Default)

1·2차 패스는 Vis·Limbic 2개 네트워크(87개 영역)만 다뤘다. 6차 패스에서
동일한 원본(Schaefer 400-parcel 센트로이드 + `liu_meg-scfc`의 400x400
이진 합의 SC 행렬 + 7-network 정수 라벨)에서 **나머지 5개 네트워크를
전부** 추가했다:

| 네트워크 | 실제 라벨 정수 | 영역 수 | 실측 연결 수 |
|---|---|---|---|
| SomMot(체성감각/운동) | 1 | 77 | 496 |
| DorsAttn(배측 주의) | 2 | 46 | 118 |
| SalVentAttn(복측 주의/현출성) | 3 | 47 | 137 |
| Cont(집행제어) | 5 | 52 | 198 |
| Default(디폴트모드) | 6 | 91 | 519 |

7개 네트워크 영역 수를 다 더하면 **61+77+46+47+26+52+91 = 400** —
Schaefer 400-parcel 원본의 전체 파셀 수와 정확히 일치(빠지거나 중복된
파셀이 없음을 확인하는 자체 검증). `schaefer_<network>_regions.csv`/
`_edges.csv` 명명 규칙으로 나머지 네트워크와 동일하게 벤더링.

## 개별 영역 실제 해부학 라벨 (AAL 좌표 조회, 5차 패스)

Schaefer 400-parcel 이름은 "Vis_1".."Vis_31"처럼 네트워크 안에서 순번만
붙어 있고(Limbic의 OFC/TempPole 같은 세부 명칭이 없음), 그래서 마우스오버
툴팁이 어느 영역이든 똑같은 안내문만 보여줬다. 이를 실제 좌표 조회로
해결했다 — 각 영역의 실제 MNI 무게중심을 **AAL(Automated Anatomical
Labeling) 아틀라스**(Tzourio-Mazoyer et al. 2002, *NeuroImage* 15:273)에서
찾아 실제로 어느 해부학적 구조 안/근처에 있는지 라벨을 붙였다.

- 원본: FieldTrip 툴박스가 재배포하는 `ROI_MNI_V4.nii`(MNI152 2mm, 116개
  실제 영역) + `ROI_MNI_V4.txt`(라벨 이름표) —
  `github.com/fieldtrip/fieldtrip/tree/master/template/atlas/aal`, 공개,
  로그인 불필요. `app/data/sources/human/aal/`에 벤더링.
- 1·2차 패스의 87개(Vis+Limbic)뿐 아니라 6차 패스로 늘어난 **400개
  영역(Yeo-7 전체) 전부 실제 좌표 조회로 해결(0개 미해결)** — 결과는
  Calcarine(일차시각피질), Precentral/Postcentral(1차 운동/체성감각피질),
  Angular/Precuneus/Cingulum_Post(디폴트모드 핵심부), Insula(현출성
  네트워크), Frontal_*_Orb/Rectus(안와전두피질) 등 실제 신경해부학 명칭과
  부합.
- **정직하게 밝힘**: 이건 "이 파셀의 중심점이 실제로 어느 구조 안/가장
  가까이 있는가"라는 좌표 조회이지, "이 Schaefer 파셀이 그 AAL 영역과
  똑같다"는 뜻이 아니다 — 두 아틀라스의 경계선은 서로 다르다. 짧은 한글
  기능 설명(`anatomical_note`)은 해당 AAL 이름에 대한 일반적인 신경해부학
  교과서 지식이며, 이 파셀 자체를 측정해서 나온 값이 아니다. 조회에
  실패하면(주변 3복셀 이내에 라벨된 조직이 없으면) 추측하지 않고
  `null`로 남긴다(지금까지 400개는 전부 해결돼 실제로는 발생하지 않음).

## 병변-증상 연관(질환) 목록 (7차 패스)

각 영역의 실제 AAL 라벨을 기준으로, 그 부위 손상과 고전적으로 연관된
질환/증상을 정리했다 — 클릭하면 해당 부위가 씬에서 강조 표시된다.
`scripts/human_anatomical_labels.py`의 `DISORDERS`에 20개를 정리(대뇌색맹,
피질맹, 안면실인증, 브로카/베르니케 실어증, 게르스트만 증후군 등).

- **국소(focal) 15개**: 특정 소수 부위 손상과 직접 연결되는 고전적
  병변-증상 사례(예: 안와전두피질 손상 → 피니어스 게이지 사례로 유명한
  안와전두 증후군).
- **복합(complex) 5개**: 알츠하이머병·조현병·주요우울장애·자폐스펙트럼
  장애·PTSD — 여러 네트워크에 걸쳐 문헌상 반복적으로 이상이 보고되는
  부위들이며, 단일 부위 손상이 원인이 아니라 유전·발달·신경전달물질·환경이
  겹치는 다인성 질환임을 설명에 명시. 국소 병변 증후군과 프론트엔드에서도
  섞이지 않게 구분 표시.
- **정직하게 밝힘**: 모든 항목의 설명에 "실제 원인·경과는 이보다 훨씬
  복잡할 수 있다"는 문구를 명시했다 — 이 프로젝트의 진단이 아니라 고전적
  임상신경학 지식을 교육용으로 재구성한 것이다. `region_ids`는 이 데이터셋에
  실제로 존재하는, 해당 AAL 라벨과 일치하는 영역만 담는다(가상의 영역
  없음) — 매칭되는 영역이 하나도 없는 질환은 아예 목록에서 제외.

## 두개골/뇌 표면 메시 (dive-in reveal, 2차 패스)

웜(v1)의 `LayerControlPanel`·초파리(v2)의 dive-in reveal과 동일한 UX(겉모습→
조직→신경계 슬라이더)를 인간 거시 커넥톰 페이지에도 적용했다. 초파리 페이지의
겉모습(더듬이/눈)은 실측 스캔이 없어 도식적 근사였지만, 인간 머리/뇌 표면은
**실제 등록된 MRI 템플릿 볼륨**이 공개돼 있어 그것을 썼다.

- 원본: **MNI152NLin2009cAsym** 템플릿(res-02, 2mm), templateflow 공개 배포
  (`templateflow.s3.amazonaws.com/tpl-MNI152NLin2009cAsym/...`, 로그인 불필요,
  Public Domain) — `T1w.nii.gz`(강도 볼륨), `desc-brain_mask.nii.gz`(이진 뇌
  마스크), `label-GM_probseg.nii.gz`(회백질 확률). 셋 다 동일한 97x115x97
  (2mm) 격자, 위 macro 커넥톰 영역과 같은 MNI 좌표계.
- **marching cubes**(scikit-image)로 세 등위면 추출(`scripts/human_anatomy_
  mesh.py`): skin(T1w 강도 임계 1200), brain(뇌 마스크 이진 경계),
  gray_matter(회백질 확률 0.4 임계 — 실제 대뇌피질 뉴런 세포체가 위치하는
  층이라 "신경계" 단계로 사용). 격자 간격 3으로 샘플링해(step_size=3)
  JSON 페이로드 크기를 줄임 — 정밀 진단용이 아니라 반투명 리빌 셸이므로
  허용되는 손실.
- **한계**: 이 템플릿은 특정 개인의 두개골 스캔이 아니라 **여러 명을 비선형
  정합해 평균한 인구 집단 템플릿**이다 — 그래서 경계가 실제 개인 스캔보다
  부드럽게 뭉개져 있고, T1w의 피부/공기 경계 임계값도 문헌 스펙이 아니라
  "실제 성인 머리 크기(약 190x228x190mm)와 맞는지"를 눈으로 확인해 고른
  값이다. 위치·전체 비율(실제 MNI mm)은 실제 데이터고, 표면의 정밀한 굴곡만
  근사임을 명시.
- 좌표 변환: 위 macro 커넥톰 영역들과 정확히 같은 중심/축척(뇌 마스크 자체의
  실제 바운딩박스 기준, `human_anatomy_mesh.compute_reference_frame`)을
  공유 — 어떤 네트워크를 선택해도, 그리고 겉모습/뇌/회백질 셸 모두 같은
  장면 좌표계에 있어 서로 어긋나지 않는다.

## 2. 미시 샘플 — H01 인간 대뇌피질 실제 EM 재구성 (측두엽)

Shapson-Coe et al. 2021, *Science*, "A petavoxel fragment of human cerebral
cortex reconstructed at nanoscale resolution" (Google/하버드). 간질 수술 중
해마 병변에 접근하기 위해 제거된 **측두엽(temporal cortex)** 조직 약 1mm³를
나노미터 해상도로 전자현미경 촬영 후 재구성한 것.

- 원본: `storage.googleapis.com/h01-release/...` (공개 GCS 버킷, 로그인
  불필요). 이 프로젝트가 사용한 것은 그중 **사람이 직접 검수(proofread)한
  뉴런 104개**의 3D 골격(skeleton, SWC 포맷) —
  `data/20210601/proofread_104/skeletons/104_proofread_neurons_swc.zip`.
- **정직하게 밝힘: 시각 영역이 아니다.** 위 거시 커넥톰(시각 네트워크)과
  해부학적으로 다른 부위이며, 억지로 연결짓지 않는다 — 프론트엔드에서도
  "실제 인간 피질 미세 샘플(측두엽)"로 독립 표기, 시각 네트워크 페이지에서
  영역을 클릭해도 나타나지 않는다.
- 104개 뉴런 각각은 원본이 여러 SWC 파일(가지별 단편)로 나뉘어 있고 합쳐서
  총 384만 개 좌표점 — 그대로 벤더링하기엔 너무 커서 **100포인트당 1개
  간격으로 다운샘플링**해 41,007개 점으로 줄였다(`h01_micro_sample_points.csv`).
  실제 골격 가지 형태의 근사치이지, 원본 그대로의 완전한 해상도가 아니다.
- **시냅스 연결 정보는 포함하지 않았다.** 원본에는 뉴런 간 실제 시냅스
  데이터도 있으나(~1억 5천만 개 추정), Apache Avro 샤드 포맷으로 세그먼트
  ID 교차 참조가 필요해 이번 패스의 "간단한 CSV 벤더링" 범위를 벗어난다 —
  향후 패스 후보로 남긴다. 이번 패스는 **뉴런 형태(morphology)만** 보여준다.

### 2-1. 4차 패스 추가 — 실제 시냅스 접촉점 (뉴런-뉴런 회로 아님)

원본: `gs://h01-release/data/20210729/c3/synapses/exported/`("Synaptic
connections database", Apache Avro, 166개 샤드, 실측 약 1억 6,600만 건,
`fetch_h01_synapses.py`).

- **먼저 확인한 것 — 104개 뉴런 사이의 직접 시냅스는 사실상 0건.** 166개 중
  7개 샤드(약 700만 건, 4.2%)를 전수 검사한 결과 양쪽 다 104개 proofread
  뉴런에 속하는 시냅스가 단 한 건도 없었다. 이 104개는 애초에 "서로 연결된
  회로"로 고른 게 아니라 1mm³ 조직 안에서 형태학적 다양성 확보 목적으로
  각각 개별 검수된 뉴런들이라, 회로도(누가 누구와 연결되는지)를 그릴 수
  있는 데이터가 아니다.
- **대신 반영한 것**: 한쪽만 104개 중 하나인 실제 시냅스 접촉점 —
  `fetch_h01_synapses.py`가 166개 샤드 전체를 스캔해 실제로 매칭되는
  행만 뽑는다(추정치가 아니라 전수 조사). 반대편이 104개 중 하나가 아니면
  "미검수 세그먼트"로 정직하게 표시(`partner_is_proofread=False`, 실측상
  거의 항상 이 값).
- **좌표계 보정(실측으로 검증)**: 이 시냅스 export의 `location.x/y`는
  proofread 스켈레톤(`h01_micro_sample_points.csv`)보다 더 미세한 해상도
  좌표계다 — 실제로 매칭되는 1,197개 표본에서 `x/4, y/4`(z는 그대로)를
  적용하면 99.7%가 해당 뉴런의 실제 스켈레톤 바운딩박스 안에 들어간다
  (500 단위 여유를 주면 100%) — H01의 다중 해상도(mip) 피라미드에서 두
  데이터셋이 서로 다른 배율의 좌표계를 쓰기 때문으로 보인다. 이 보정은
  `build_human_dataset.py`에서 적용하고, 벤더링된 원본 CSV는 raw 값 그대로
  보존한다(이 프로젝트의 기존 관례와 동일).
- **흥분성/억제성 라벨은 넣지 않았다.** data.html은 "Synapses as points"
  export(`c3/synapses/precomputed`, 이번 패스에서 쓰지 않음)에만 실제
  E/I 분류가 있다고 명시한다. 우리가 쓰는 Avro "connections database"의
  `type`/`subtype` 정수 필드는 표본 검사 결과 pre=1, post=2로 항상
  고정돼 있어 — 신경전달물질 종류가 아니라 "이 쪽이 시냅스 전/후 중 어디"
  라는 역할 마커로 보인다. 대신 실제로 검증 가능한 `class_label`
  (AXON/DENDRITE, 104개 뉴런이 이 접촉점에서 신호를 보내는 쪽인지 받는
  쪽인지)만 `role` 필드로 노출한다.
- **신뢰도**: 원본의 자동 분류기 `confidence`(0-1)를 그대로 실어 프론트에서
  투명도 등으로 반영할 수 있게 했다 — 이 프로젝트가 계산한 값이 아니라
  원본 자동 분류기 출력 그대로.

## 3. 인간 게놈 — 신경계 관련 유전자

**NCBI Gene** (`Homo_sapiens.gene_info`, 실제 염색체·세포유전학적 밴드
위치·설명·유전자 종류) + **NCBI gene2go** (Gene Ontology 기능 주석,
실제 논문 기반 큐레이션) + **UCSC cytoBand** (hg38 염색체 이데오그램 밴드
좌표, 실제 핵형 데이터).

- 원본: `ftp.ncbi.nlm.nih.gov/gene/DATA/GENE_INFO/Mammalia/Homo_sapiens.gene_info.gz`,
  `ftp.ncbi.nlm.nih.gov/gene/DATA/gene2go.gz`,
  `hgdownload.soe.ucsc.edu/goldenPath/hg38/database/cytoBand.txt.gz` — 전부
  공개, 로그인 불필요.
- **신경계 유전자 선정**: 실제 GO 주석 기준으로 필터링(추측 아님) —
  `GO:0007399`(nervous system development, 352개) ∪
  `GO:0007268`(chemical synaptic transmission, 192개) = **총 511개 유전자**
  (`human_nervous_system_genes.csv`).
- **염색체 이데오그램**: hg38 실제 세포유전학적 밴드(cytoBand) 1,549개를
  그대로 사용 — 각 유전자를 `map_location`(예: BDNF는 `11p14.1`)에 매칭해
  실제 염색체 물리적 비율에 가깝게 배치.
- **"미확인/가설" 라벨 기준**: `description` 필드가 실제 채워져 있고
  `type_of_gene`이 `protein-coding`이면 "기능 주석 있음"으로, 설명이
  비어있거나 `type_of_gene`이 `ncRNA`/`pseudogene`/`unknown` 등이면
  "기능 불명·가설 단계"로 표기 — 이 프로젝트가 직접 지어낸 가설이 아니라,
  NCBI 큐레이션 데이터 자체의 완성도를 그대로 반영한 것이다.

### 3-1. 2차 패스 추가 — 시각 지각(Visual Perception) 유전자

거시 커넥톰의 Vis 네트워크와 짝을 이루도록, 같은 gene2go에서 실제 GO 주석
`GO:0007601`(visual perception)에 해당하는 인간 유전자 **140개**를 추가로
필터링했다. 이 중 1차 패스의 511개(신경계 발달·화학적 시냅스 전달)와 이미
겹치는 5개를 빼고, **새로 추가되는 135개만** `human_visual_system_genes.csv`
에 담았다(ABCA4, OPN1SW 등 실제 광수용/망막 유전자 포함) — 최종 게놈
유전자 총합 **646개**.

- **정직하게 밝힘(단순화 지점)**: 135개는 "1차 패스 511개 목록에는 없던"
  기준으로만 걸렀다 — 즉 이미 511개 안에 있는 유전자 중 실제로는
  `GO:0007601` 주석도 가진 유전자가 있을 수 있지만(생물학적으로는 두
  카테고리에 다 속함), 이번 패스는 그런 유전자의 `go_tags`에
  `visual_perception`을 추가로 붙이지 않았다 — 중복 행 없이 파일을
  단순하게 유지하기 위한 절충이며, "신경계 511개"와 "시각 지각 135개"가
  생물학적으로 완전히 배타적이라는 뜻은 아니다.
- 프론트엔드 게놈 페이지에 `go_tags` 기준 기능별 필터(신경계 발달 /
  화학적 시냅스 전달 / 시각 지각)를 추가해, 어느 조합이든 켜고 끌 수 있게
  했다.

## 4. BDNF 활동의존적 발현 경로 (커맨드 시뮬레이션)

신경 활동 → CREB(cAMP response element-binding protein) 인산화 → BDNF
유전자 발현 → TrkB(NTRK2) 수용체 결합 → 시냅스 가소성으로 이어지는 경로는
신경과학에서 잘 확립된, 자주 인용되는 활동의존적 유전자 발현 기전이다.

- Tao, X., Finkbeiner, S., Arnold, D.B., Shaywitz, A.J., Greenberg, M.E.
  (1998). "Ca2+ influx regulates BDNF transcription by a CREB family
  transcription factor-dependent mechanism." *Neuron* 20(4).
- Greenberg, M.E., Xu, B., Lu, B., Hempstead, B.L. (2009). "New insights in
  the biology of BDNF synthesis and release: implications in CNS function."
  *Journal of Neuroscience* 29(41).

BDNF/CREB1/NTRK2 세 유전자의 실제 염색체 위치는 `bdnf_pathway_genes.csv`에
따로 정리했다(CREB1·NTRK2는 이번 패스의 GO 필터 511개 목록에는 포함되지
않음 — 전사인자/수용체로서 다른 GO 카테고리에 분류되어 있을 뿐, 존재하지
않는 유전자가 아니다). 이 커맨드는 **fly_engine.py의 규칙 기반 내레이션과
동일한 패턴** — 실제 경로 순서를 고정된 타이밍으로 재생하는 것이지, 유전자
발현을 실제로 시뮬레이션(예: ODE 기반 전사 동역학)하는 것은 아니다.

## 5. Arc/Arg3.1 시냅스 가소성 경로 (커맨드 시뮬레이션, v4에서 추가)

NMDA 수용체(GRIN2B/GluN2B) 활성화 → 칼슘 유입 → CaMKII(CAMK2A) 인산화 →
Arc/Arg3.1(ARC) 즉시초기유전자 발현 → 시냅스 후막 축적 → 시냅스 가소성
(LTP/LTD) 조절로 이어지는 경로는 BDNF 경로와 함께 신경과학에서 가장 널리
인용되는 활동의존적 유전자 발현 기전 중 하나다.

- Bramham, C.R., Worley, P.F., Moore, M.J., Guzowski, J.F. (2008). "The
  Immediate Early Gene Arc/Arg3.1: Regulation, Mechanisms, and Function."
  *Journal of Neuroscience* 28(46):11760-11767.

GRIN2B/CAMK2A/ARC 세 유전자의 실제 염색체 위치는 `arc_plasticity_genes.csv`에
정리했다(GRIN2B는 이번 패스의 GO 필터 511개 목록에 이미 포함되어 있고,
CAMK2A·ARC는 BDNF 경로의 CREB1·NTRK2와 같은 이유로 별도 목록 — 존재하지
않는 유전자가 아니라 다른 GO 카테고리 소속). BDNF 커맨드와 완전히 동일한
패턴(고정 타이밍 내레이션, ODE 기반 발현 시뮬레이션 아님)으로 구현했다.

## 6. AAL → 4대엽(전두엽/두정엽/측두엽/후두엽) 매핑 (챗봇 패널, v4에서 추가)

일반인에게 익숙한 해부학적 4대엽 분류는 이 프로젝트가 지금까지 쓴
Yeo-7 기능 네트워크와 다른 축이다. AAL 아틀라스 자체가 116개 영역을
Frontal/Parietal/Temporal/Occipital/Insula/Limbic/SCGM/Cerebellum으로
분류하는 공식 체계를 갖고 있다(Tzourio-Mazoyer et al. 2002, *NeuroImage*
15(1):273-289; Rolls, Huang, Lin, Feng & Joliot 2020의 AAL3 갱신판도 같은
틀 유지). `backend/app/data/human_lobes.py`에 이 프로젝트에 실제로 매칭된
38개 AAL 기본 라벨(19단계 좌표 조회 결과)만 이 분류에 따라 정리했다 —
Insula/Cingulum_*/ParaHippocampal(AAL의 Limbic·뇌섬엽 카테고리)은 4대엽
개념 밖이라고 정직하게 별도 표시했다. Paracentral_Lobule·Rolandic_Oper
두 영역은 해부학적으로 두 엽 경계에 걸쳐 있어 원 논문의 표를 따라 전두엽
쪽으로 분류했다는 점도 모듈 docstring에 명시.

## 7. 챗봇 코퍼스 임베딩 (의미 검색, docs/31에서 추가)

`human_chat_embeddings.json`은 "실제 외부 데이터셋"이 아니라 **이
프로젝트가 이미 가진 실제 데이터(영역 해부학적 설명·질환 설명·유전자
설명, 위 1~6절에서 이미 출처를 밝힌 것들)를 OpenAI
`text-embedding-3-small`(dimensions=256)로 임베딩한 빌드 산출물**이다.
`backend/scripts/build_human_chat_embeddings.py`로 생성하며, 코퍼스
텍스트가 바뀌면(새 region/disorder/gene 설명 추가·수정) 수동으로
다시 실행해야 한다 — 자동 재빌드 트리거는 없다. 1,066개 문서, 실제
생성 시점 파일 크기 약 5MB. 원본 텍스트의 출처는 전부 위 1~6절(및
docs/19·docs/21단계)에 이미 기록돼 있으므로 별도 인용 없음 — 이 파일
자체는 "그 텍스트들의 벡터 표현"일 뿐이다.

## docs/48 추가 원자료 (가설 H1-1~H1-5 재분석용) + docs/49 네트워크 간 간선 복구

- `liu2023_sc_cons_400_nosubc.npy`, `liu2023_sc_avggm_400_nosubc.npy`, `liu2023_dist_400.npy`,
  `liu2023_fc_cons_400.npy` -- `github.com/netneurolab/liu_meg-scfc` `data/` 원본 그대로(공개, 로그인 불필요).
  위 1절의 거시 커넥톰과 같은 원본이지만 **전체 400×400**이다. 이 프로젝트의 `human_macro_connectome.json`은
  네트워크별 CSV에서 **네트워크 내부 간선만**(2,041개) 가져와, 원본의 네트워크 간 간선 3,018개가 빠져 있다
  (docs/48에서 발견 -- 영역 id-1이 행렬 인덱스이고 내부 간선은 원본과 정확히 일치함을 확인).
- `hansen2022_receptor_data_scale400.csv` -- Hansen et al. 2022, Nat Neurosci 25:1569
  (`github.com/netneurolab/hansen_receptors` `results/receptor_data_scale400.csv`). 19종 수용체/수송체
  PET 밀도(열 순서: 5HT1a, 5HT1b, 5HT2a, 5HT4, 5HT6, 5HTT, A4B2, CB1, D1, D2, DAT, GABAa, H3, M1, mGluR5,
  MOR, NET, NMDA, VAChT), Schaefer-400 7-network 순서.
- **docs/49 복구**: `schaefer_cross_network_edges.csv`(3,018개, `roi_label_a,roi_label_b`) -- 위
  `liu2023_sc_cons_400_nosubc.npy`에서 서로 다른 Yeo-7 네트워크에 속한 영역 쌍만 뽑은 것. 1·2·6차 패스가
  네트워크마다 내부 간선만 벤더링해서 처음부터 한 번도 들어간 적 없던 간선이다(손상이 아니라 누락).
  이제 `build_human_dataset.py`가 이 파일까지 읽고, 결과 간선 집합이 원본 행렬 상삼각(5,059개)과 정확히
  같아야만 빌드가 통과한다(재발 방지 -- 이전엔 영역 수 합계 400만 검증했다).
