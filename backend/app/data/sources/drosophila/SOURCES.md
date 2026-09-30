# Drosophila (v2) 데이터 출처 및 한계

C. elegans(`app/data/sources/SOURCES.md`)와 동일한 원칙: 실제 공개 데이터만 사용하고,
계산된 값(레이아웃 좌표 등)은 "측정된 값이 아님"을 명시한다.

## 원본 소스

**Hemibrain connectome v1.2** (Janelia FlyEM / neuPrint), CC-BY 4.0.
인용: Scheffer, L.K., Xu, C., Januszewski, M., et al. (2020). *A connectome and
analysis of the adult Drosophila central brain.* eLife 9:e57443.

- 다운로드: `https://storage.googleapis.com/hemibrain/v1.2/exported-traced-adjacencies-v1.2.tar.gz`
  (로그인 불필요, 공개 GCS 버킷 — `storage.cloud.google.com` 링크는 로그인을 요구하니 주의)
- 원본 파일: `traced-neurons.csv`(21,740 neurons: bodyId, type, instance),
  `traced-total-connections.csv`(3,550,404 neuron-neuron directed connections,
  weight = 두 뉴런 사이 총 시냅스 수). `hemibrain_export_README.txt`에 원본 README 보관.
- 원본 CSV 자체는 용량 문제(79MB)로 vendoring하지 않고, 아래 "후각 회로 서브셋" 필터링
  결과만 커밋한다. 재현하려면 위 URL에서 다시 받아 아래 필터를 그대로 적용하면 된다.

## 후각 회로 서브셋 (v2 1차 패스 범위)

전체 hemibrain(central brain 전체, 2.5만+ 뉴런)은 v1과 같은 "뉴런당 개별 HH 시뮬레이션 +
뉴런당 3D 메시" 방식으로 다루기엔 규모가 맞지 않아, 가장 잘 문서화된 **후각 처리 경로**만
`type` 컬럼의 명명 규칙으로 필터링했다 (`olfactory_subset_neurons.csv`,
`olfactory_subset_connections.csv`):

| 분류 | 필터 규칙 | 개수 | 비고 |
|---|---|---|---|
| ORN (후각수용뉴런) | `type`이 `ORN`로 시작 | 2 | hemibrain은 central brain만 촬영해 ORN 세포체 대부분이 잘려나가 거의 안 남아있음 — **정직하게 밝힘**: 이 서브셋은 사실상 PN 계층부터 시작한다고 보는 게 맞음 |
| PN (단사구체 촉각엽 투사뉴런, uniglomerular antennal-lobe projection neuron) | `type`이 `<사구체명>_adPN`/`_lPN`/`_vPN`류 패턴과 정확히 매치 | 133 | 의도적으로 **좁게** 잡음: 다사구체(M_adPNxx 등)·WED(wedge, 후각과 무관한 감각 부위) PN은 제외 — "PN"을 이름에 포함한 전체 428개 중 일부만. 근거 있는 축소이지, 누락이 아님 |
| KC (버섯체 켄욘세포, Kenyon cell) | `type`이 `KC`로 시작 | 1,927 | 버섯체 학습/연합 계층 |
| MBON (버섯체 출력뉴런) | `type`이 `MBON`으로 시작 | 68 | 행동 유의성(valence) 출력 계층 |
| DAN (도파민성 뉴런, PAM/PPL 클러스터) | `type`이 `PAM` 또는 `PPL`로 시작 | 322 | 강화학습 신호(보상/처벌) 담당, 명명 자체가 도파민성임을 뜻함 |

**총 2,452 뉴런.**

### 연결 가중치 임계값

원본 3,550,404개 연결 중, 이 서브셋 뉴런끼리의 연결은 545,347개였다. Hemibrain 자체
분석(및 여러 커넥톰 연구)에서 흔히 쓰이는 관행대로 **weight(시냅스 수) ≥ 3**만 채택해
EM 분할 오류로 인한 노이즈성 단일 시냅스를 제거했다 — 결과 **139,496개 연결**
(`olfactory_subset_connections.csv`). 이 임계값은 자의적 창작이 아니라 hemibrain 커넥톰
분석에서 통용되는 "신뢰 가능한 연결" 기준이다.

## 시각 회로 서브셋 (v2 2차 패스 범위)

같은 hemibrain v1.2 원본에서, 이번엔 **시각 처리 경로**를 필터링했다
(`visual_subset_neurons.csv`, `visual_subset_connections.csv`). hemibrain은
central brain 위주로 촬영되어 medulla 내재뉴런(Mi/Tm/T4/T5/L1-5/C2/C3/Dm/Pm
등, 광수용체 바로 다음 처리 단계)은 **전혀 포함되어 있지 않다** — 실제로
raw `traced-neurons.csv`에서 이 명명 패턴들을 검색하면 0건이다 (직접 확인
함, 후각 서브셋의 ORN이 거의 잘려나간 것과 같은 종류의 촬영 범위 한계).
대신 hemibrain에는 로불라/로불라판(lobula/lobula plate)에서 중심뇌로
신호를 내보내는 **시각 투사뉴런(VPN)**과, 뇌에서 흉부신경절(VNC)로 신호를
내려보내는 **하행뉴런(DN)**은 잘 남아있다 — 이번 서브셋은 이 두 계층으로
구성된다.

| 분류 | 필터 규칙 | 개수 | 비고 |
|---|---|---|---|
| VPN (시각 투사뉴런) | `type`이 `LC\d`, `LT\d`, `LPLC\d`, `LLPC\d`, `LPC\d` 패턴과 매치 | 2,948 | 로불라/로불라판 출력 컬럼 타입 전체 (107개 서로 다른 타입) |
| DN (하행뉴런) | `type`이 `DNp`로 시작하거나 정확히 `Giant Fiber` | 59 | Giant Fiber는 단일 식별 뉴런으로 이름 자체가 그대로 남아있음 |

**총 3,007 뉴런.** VPN->DN 직접 연결(weight>=3)은 1,710개, 총 가중치
26,107 — `LC4`가 압도적으로 크며(전체의 절반 가까이), 이는 실제 출판된
문헌에서 LC4가 Giant Fiber 도피 경로의 핵심 입력으로 잘 알려진 것과
일치한다(우연이 아니라 실측 연결성 기준으로 커맨드 4개를 골랐다 — 아래
참고).

### 커맨드 4개 선정 기준

`VisualCommand`의 4개 버튼(`LC4`/`LC6`/`LPLC2`/`LC9`)은 문헌 인지도만으로
고른 것이 아니라, **VPN->DN 계층으로의 총 실측 시냅스 가중치가 가장 큰
타입 상위권**에서, 동시에 문헌에 행동적 역할이 출판되어 있는 것만 골랐다:

- `LC4`: 루밍(다가오는 물체)/도피 검출기, Giant Fiber 경로 핵심 입력 —
  von Reyn et al. 2014
- `LC6`: 루밍/도피 검출기, Giant Fiber 경로 입력 — von Reyn et al. 2017
- `LPLC2`: 양안 루밍 검출기, Giant Fiber에 직접 시냅스 확인 — Ache et al. 2019
- `LC9`: 소형 이동물체 검출/추적 — Klapoetke et al. 2017

각 커맨드가 사용하는 1-hop 경로(`app/simulation/fly_engine.py`의
`_VISUAL_PATHWAYS`)는 실제 hemibrain 연결 중 해당 VPN 타입에서 나가는
**가장 가중치가 큰 단일 VPN->DN 시냅스**를 그대로 사용한다 (LC4->DNp04
weight 98, LC6->DNp06 weight 10, LPLC2->Giant Fiber weight 36, LC9->DNp11
weight 18 — 모두 원본 `traced-total-connections.csv`에서 직접 확인).

### 회로 간 교차 연결 (cross_circuit_bridge_connections.csv)

후각 서브셋과 시각 서브셋을 각각 독립적으로 필터링하면, 두 서브셋 사이에
실제로 존재하는 직접 연결(예: MBON이 DN에 시냅스하는 경우)이 누락된다.
같은 원본 파일에서 "한쪽이 후각 서브셋, 다른 한쪽이 시각 서브셋에 속하는
weight>=3 연결"만 별도로 추출해 91개를 확인했고, 이를
`cross_circuit_bridge_connections.csv`로 벤더링했다 — 조작된 연결이 아니라
naive한 서브셋별 필터링이 놓칠 뻔한 **실제 hemibrain 엣지**다.

## 항법(나침반) 회로 서브셋 (v2 4차 패스 범위)

같은 hemibrain v1.2 원본에서 세 번째 회로 서브셋으로, 초파리 중심복합체(central
complex)의 헤딩(heading)/나침반 회로를 필터링했다 — Hulse et al. 2021 eLife
"A connectome of the Drosophila central complex reveals network motifs suitable
for flexible navigation and context-dependent action selection"이 이 회로 전체를
hemibrain 데이터로 상세히 분석한 바로 그 시스템이다.

| 분류 | 필터 규칙 | 개수 | 비고 |
|---|---|---|---|
| ER (고리뉴런) | `type`이 `ER\d`로 시작 | 257 | 타원체(ellipsoid body)로 시각 랜드마크 등 입력을 전달하는 것으로 알려진 뉴런. 이 서브셋엔 그 상류(시각 경로)는 포함하지 않음 — 후각 서브셋의 ORN처럼 "입력 경계"만 존재 |
| RING (나침반 고리) | `type`이 `EPG`/`PEN`/`PEG`/`Delta7`로 시작 | 152 | 타원체-원판(PB) 나침반 링 어트랙터를 구성하는 핵심 4종. EPG=헤딩(compass) 신호, PEN=각속도 입력, PEG/Delta7=링 내부 억제·이득 조절 |
| PFN (헤딩-목표 통합) | `type`이 `PFN`으로 시작 | 437 | 헤딩 신호와 내부 목표/상태 신호를 결합하는 부채모양체(fan-shaped body) 투사뉴런. 여러 하위타입(PFNa/PFNd/PFNm 등) 존재 |
| PFL (조향 출력) | `type`이 `PFL`로 시작 | 50 | 실제 조향(steering) 명령을 담당하는 것으로 출판된 출력뉴런(PFL1/2/3) — Rayshubskiy et al. 2020, Mussells Pires et al. 2024 |

**총 896 뉴런.** 의도적으로 제외한 것: hDelta/vDelta(590개)·광범위한 FB 접선뉴런(573개) —
부채모양체 국소처리를 담당하는 것으로 알려져 있으나 개별 서브타입 단위로 확신 있게
인용할 수 있는 행동적 역할을 찾지 못해, "실측 데이터가 있어도 확신 없는 서술은 하지
않는다"는 원칙에 따라 이번 패스 범위 밖으로 뒀다(향후 패스 후보).

### 커맨드 4개 선정 기준

`HeadingCommand`(`EPG_L4`/`EPG_R4`/`EPG_R6`/`EPG_L2`)는 각각 특정 원판(protocerebral
bridge) 웨지를 담당하는 실제 EPG 뉴런이다 — hemibrain의 `instance` 명명 자체가 웨지
번호를 그대로 담고 있다(예: `EPG(PB08)_L4`). 후각/시각과 같은 원칙으로, 실제
EPG→PFL 직접 시냅스 중 가중치가 큰 것 위주로 4개를 골랐다(L4→PFL2 w78, R4→PFL2 w50,
R6→PFL3 w48, L2→PFL1 w40) — 좌/우 웨지를 섞고 PFL1/2/3 세 하위타입을 모두 포함해
다양성을 확보했다.

### 회로 간 교차 연결

후각·시각 서브셋과 마찬가지로, 이 서브셋과 기존 두 서브셋 사이의 실제 weight≥3
연결을 별도로 스캔해 `cross_circuit_bridge_connections_navigation.csv`로 벤더링했다
(후각과 4개, 시각과 44개 — 시각 쪽이 더 많은 것은 둘 다 중심뇌 후방/조향 관련
회로라 실제로 더 가까이 위치·연결되어 있기 때문으로 보이며, 이 역시 조작 없는 실제
hemibrain 엣지다).

## 정직하게 밝혀야 할 한계 (v1과 동일한 원칙)

- **3D 좌표는 실제 해부학적 좌표가 아니다.** hemibrain 공개 flat CSV에는 소마(cell body)
  XYZ 좌표가 포함되어 있지 않다(neuPrint API로 인증 후 조회해야 함). v1의 **첫 패스와
  동일하게** 연결 관계 기반 근사 배치(입력 PN → KC → MBON 순서로 축을 두고, 같은 시냅스
  파트너를 공유하는 뉴런끼리 가까이 배치)를 계산해 사용한다. 실제 스켈레톤/메시 좌표로
  교체하는 것은 이후 패스 과제.
- **신경전달물질은 대부분 `unknown`이다.** hemibrain 공개 flat 파일에는 신경전달물질
  예측값이 없다(별도 논문/데이터셋에 존재하나 이번 패스에서는 가져오지 않음). 예외적으로
  **DAN(PAM/PPL)만 `dopamine`으로 표기** — 이건 추측이 아니라 hemibrain 자체의 세포유형
  명명(PAM/PPL = dopaminergic neuron cluster)이 곧 신경전달물질 정체성이기 때문이다. 나머지
  전부(ORN/PN/KC/MBON)는 `unknown`으로 정직하게 남긴다 — "PN은 보통 콜린성이다" 같은
  문헌상 통설이 있지만, 이 프로젝트가 C. elegans에서 쓴 owmeta처럼 **개별 세포 단위로
  실측/큐레이션된 출처**가 아니라서 채택하지 않았다.
- **시냅스 종류(화학/전기)를 구분하지 않는다.** hemibrain adjacency 테이블은 gap
  junction(전기 시냅스)을 별도로 표시하지 않는다 — C. elegans의 edge list와 다른 점.
  이번 패스에서는 전부 `chemical`로 표기한다.
- **effector(출력 근육/조직)가 없다.** 이 서브셋은 후각 자극 → 회로 활성 → 행동 유의성
  신호까지이며, 실제 운동 출력(근육)은 모델링하지 않는다 — v1의 이동/근육 피지컬은 초파리
  v2 1차 패스의 범위 밖.
- **뉴런의 기능적 역할(NeuronType: sensory/inter/motor) 분류는 회로 단계 기반 근사다.**
  ORN=sensory, PN/KC/DAN=inter, MBON=motor(출력)로 매핑했다 — 실제 생리학적 "motor neuron"이
  아니라 "회로의 출력 계층"이라는 의미로 사용한 것임을 명시한다. 시각 서브셋도 같은 원칙으로
  VPN=sensory(이 서브셋의 입력 경계), DN=motor(회로 출력 근사치)로 매핑했다.
- **VPN/DN에는 medulla 내재뉴런(광수용체 다음 처리 단계)이 없다.** 위 "시각 회로 서브셋"
  절에서 설명했듯 hemibrain 자체가 이 영역을 촬영하지 않았다 — 서브셋을 좁게 잡은 게 아니라
  원본 데이터에 존재하지 않는다. DN의 실제 하류(흉부신경절의 비행/도약 운동뉴런)도 같은
  이유로 없다.
