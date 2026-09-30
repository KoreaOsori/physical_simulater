# physical_simulater

생명체의 뇌지도(커넥톰)를 3D로 시각화하고, 신경 신호 → 시냅스 → 신경전달물질 → 근육 반응 →
행동 발현까지의 흐름을 로컬 환경에서 재현하는 연구용 프로젝트입니다.

**진행 보고 문서**: [docs/](docs/00-overview.md) 폴더에 각 개발 단계의 결과보고가 번호
순서(00, 01, 02, ...)로 정리되어 있습니다.

- v1 대상 생물: **예쁜꼬마선충 (C. elegans)**, 302개 뉴런 커넥톰
- v2 대상 생물: **노랑초파리 (Drosophila melanogaster)**, hemibrain 다중 회로 서브셋
- v3 대상: **인간 (Homo sapiens)** — 뉴런 단위 전체 커넥톰이 존재하지 않아 거시
  영역 네트워크 + 실제 미시 EM 샘플 + 염색체 유전자 지도로 별도 구성
- 뉴런 시뮬레이션 목표 정밀도: Hodgkin-Huxley 기반 생물물리 모델 (Brian2, 초파리까지)

## 구조

```
physical_simulater/
├── frontend/   Next.js (App Router) + TypeScript + Tailwind v4 + react-three-fiber
├── backend/    FastAPI (Python) + Brian2 (뉴런 시뮬레이션)
└── docker-compose.yml
```

### frontend/src 기능별 분리

```
src/
├── app/                     Next.js 라우트 (/  , /fly)
├── features/
│   ├── lab-shell/           상단바, 페이지 오케스트레이션(WormLabPage)
│   ├── connectome-viewer/   3D 뉴런/시냅스 뷰어 (react-three-fiber)
│   ├── tissue-panel/        해부 구조(조직) 선택 패널
│   ├── simulation-control/  명령 패드, 키보드 단축키, 명령 전송 훅
│   └── event-log/           신경 이벤트 로그 패널
├── store/                   zustand 전역 상태 (simulation-store)
├── shared/lib/               API client, WebSocket client, env
└── types/                    백엔드 스키마와 동기화되는 TS 타입
```

### backend/app 구조

```
app/
├── main.py            FastAPI 앱, CORS, 라우터 등록
├── core/config.py      설정 (CORS origin, 활성 생물종 등)
├── domain/schemas.py   Neuron/Synapse/Connectome/SimulationEvent 등 pydantic 모델
├── data/
│   ├── sources/                      원본 커넥톰 데이터 (vendored) + SOURCES.md (출처/한계 문서화)
│   ├── celegans_connectome.json      빌드된 최종 데이터셋 (커밋됨)
│   └── celegans_connectome.py        위 JSON을 로드하는 런타임 로더
├── scripts/build_connectome_dataset.py  sources/ → celegans_connectome.json 빌드 스크립트
├── simulation/engine.py           명령 → 단일 시냅스 이벤트 생성 (규칙 기반, rule_based 모드에서 폴백으로 사용)
├── simulation/hh_model.py         Hodgkin-Huxley 기반 실제 302뉴런 네트워크 시뮬레이션 (기본 엔진, Brian2)
└── api/routes/         health, connectome, simulation(WebSocket 포함)
```

## 현재 상태 (v1 개발환경 구축 단계)

- [x] Next.js + Docker + 기능별 src 분리 완료
- [x] 프론트엔드 ↔ 백엔드 REST + WebSocket 연동 (명령 전송 → 신경 이벤트 스트리밍 → 3D/로그 반영)
- [x] **실제 302 뉴런 C. elegans 커넥톰 데이터 임포트 완료** — OpenWorm `c302`/`CElegansNeuroML`의
      EM 기반 연결 데이터(뉴런 302개, 근육/장/상피 등 effector 121개, 시냅스 6,933개)를
      `backend/app/data/sources/`에 vendoring하고 빌드 스크립트로 병합. 상세 출처·한계는
      `backend/app/data/sources/SOURCES.md` 참고. (3D 좌표는 이후 04단계에서 실제 EM
      soma 좌표로 교체됨 — 아래 참고.)
- [x] `simulation/engine.py`의 명령→시냅스 매핑을 실제 데이터셋에 존재하는 뉴런/시냅스로 교체
      (예: 전진=AVBL→VB2, 후진=AVAL→VA1, 배설=AVL→DVB(GABA), 번식=HSNL→vm2aL(세로토닌)).
      `test_engine_pathways_are_real_edges`가 이 매핑이 실제 데이터와 어긋나지 않는지 검증합니다.
- [x] **Hodgkin-Huxley 기반 Brian2 시뮬레이션 완료** — 302개 뉴런 전체를 HH 컴파트먼트로,
      실제 5,806개 뉴런-뉴런 시냅스(화학/전기)로 연결한 네트워크를 명령마다 실제로
      시뮬레이션합니다. 자세한 내용/한계는 [docs/03-hodgkin-huxley-simulation.md](docs/03-hodgkin-huxley-simulation.md) 참고.
      `simulation_engine` 설정(`app/core/config.py`)으로 `hodgkin_huxley`(기본)/`rule_based` 전환 가능.
- [x] **실제 해부학적 3D 좌표 + S자형 몸체 + 레이어 토글 + 신경전달물질 확산 시각화 완료** —
      뉴런 위치는 OpenWorm EM 재구성 실측 좌표(force-directed 레이아웃 대체), effector는
      실제 인접 뉴런에 앵커링. 좌측 상단 팝업 슬라이더로 겉모습→근육/조직→신경계를
      연속적으로 확인 가능. 명령 실행 시 신경전달물질 색상의 확산 애니메이션 표시.
      자세한 내용/한계는 [docs/04-anatomical-body-and-layers.md](docs/04-anatomical-body-and-layers.md) 참고.
- [x] **10초 순차 재생 · 근육→겉모습 움직임 · 뉴런 호버 툴팁 · 입/배/항문 구조 완료** —
      명령 이벤트를 즉시 한꺼번에 적용하지 않고 10초에 걸쳐 순차 재생, 근육 활성화 시
      겉모습이 국소적으로 휘고 운동(movement) 이벤트 시 전신 파동 애니메이션 재생,
      뉴런 호버 시 기능 설명 팝업(약 55개 클래스 큐레이션 + 나머지는 데이터 기반 폴백),
      입·배(생식공)·항문을 실제 뉴런 좌표(HSN, DVB)에 앵커링해 배치.
      자세한 내용/한계는 [docs/05-mechanism-playback-and-anatomy.md](docs/05-mechanism-playback-and-anatomy.md) 참고.
- [ ] 근육-근육 전기적 결합(체벽근 시트 전파) — 현재는 뉴런이 소스인 엣지만 반영 (SOURCES.md 참고)
- [ ] Effector(근육)를 활성화 여부가 아닌 막전위/수축 강도로 확장
- [ ] 겉모습 메시의 환형 마디·감각모 등 세부 표현
- [x] **302개 뉴런 전체 실제 출처 기반 설명 + 연구 동향 패널 완료** — WormBase 해부
      온톨로지(WBbt)를 임포트해 302개 뉴런 전원이 실제 분류 태그·영문 정의를 갖도록
      했고(추측 아님), 해부 구조 패널 하단에 최신 연구 동향 큐레이션 패널 추가.
      자세한 내용은 [docs/06-neuron-ontology-and-trends.md](docs/06-neuron-ontology-and-trends.md) 참고.
- [x] **겉모습 굽힘의 질량-스프링 물리 시뮬레이션 완료** — 스크립트로 그리던 몸체 굽힘을
      댐핑된 질량-스프링 사슬(49개 질점, 이웃 결합+복원+감쇠)로 교체. 근육 활성/운동
      명령이 이제 "힘"으로 주입되고 굽는 모양·복원은 시뮬레이션의 결과. 실제 이동
      (기질 마찰/추진)은 의도적으로 범위 밖 — 자세한 내용은
      [docs/07-body-physics.md](docs/07-body-physics.md) 참고.
- [ ] 실제 이동(기질 마찰/추진력 모델) — OpenWorm도 미완성인 어려운 문제, 향후 후보

## v2: 초파리 (Drosophila) — hemibrain 다중 회로 서브셋

- [x] **1차 패스 완료** — hemibrain v1.2(CC-BY) 공개 데이터에서 후각 처리 경로(ORN/PN/KC/
      MBON/DAN, 2,452뉴런·139,496시냅스)를 필터링해 v1과 같은 명령→시냅스→신경전달물질→출력
      파이프라인을 재현. 종 선택은 설정 스위치가 아니라 별도 라우트(`/api/fly/...`)로 구현해
      v1을 건드리지 않음. `/fly` 페이지에서 실제 3D 렌더링 + 4개 사구체 자극 커맨드 + 실시간
      HH 시뮬레이션까지 브라우저에서 동작 확인. 3D 좌표는 v1의 첫 패스와
      동일하게 연결 관계 기반 근사 배치(실제 해부학적 좌표 아님). 자세한 내용·한계는
      [docs/08-drosophila-v2-phase1.md](docs/08-drosophila-v2-phase1.md) 참고.
- [x] **2차 패스 완료 — 시각 회로 서브셋 추가(뉴런 수 확장)** — 같은 hemibrain에서 로불라/
      로불라판 시각 투사뉴런(VPN, 2,948개)과 하행뉴런(DN, 59개)을 추가 필터링, 후각 서브셋과
      병합해 **총 5,459뉴런·167,803시냅스**(회로 간 실제 교차 연결 91개 포함)로 확장. `LC4`/
      `LC6`/`LPLC2`/`LC9` 4개 시각 자극 커맨드는 VPN→DN 실측 연결 가중치 상위권 + 문헌
      근거(루밍/도피, 소형 이동물체 검출) 이중 기준으로 선정, 각각 검증된 1-hop 실제 시냅스
      경로 사용. 자세한 내용·한계는
      [docs/09-visual-circuit-codegen-and-docker.md](docs/09-visual-circuit-codegen-and-docker.md) 참고.
- [x] **Brian2 C++ codegen 자동 감지 완료** — 프로세스 시작 시 실제로 컴파일·실행해보고
      가능하면 cython(C++) 타겟, 안 되면 numpy로 자동 폴백(`app/simulation/codegen_target.py`).
      이 컴퓨터의 로컬 venv는 MSVC가 없어 numpy로 폴백하지만, Docker 이미지(build-essential
      +gcc, 이번 패스에서 `cython` 패키지도 requirements.txt에 추가)에서는 자동으로 더 빠른
      타겟이 적용됨.
- [x] **뉴런 툴팁 서술 보강 완료** — 회로 단계(ORN/PN/KC/MBON/DAN/VPN/DN) 7개에 대한 실제
      서술 + 커맨드가 자극하는 9개 구체 셀 타입에 대한 문헌 인용 큐레이션을 추가
      (`fly-neuron-info.ts`). 정밀 매칭을 위해 백엔드 `Neuron` 스키마에 원본 hemibrain
      `type` 문자열을 담는 `cell_type` 필드를 신설.
- [x] **3차 패스 완료 — 회로별 페이지 분리 + 시뮬레이션 스코핑** — `/fly`가 회로 선택
      랜딩 페이지가 되고, 후각/시각 회로가 각각 `/fly/olfactory`/`/fly/visual` 전용
      페이지로 분리됨(서브셋이 늘어도 페이지별 부하가 고정되도록). 데이터셋은 계속 병합
      상태를 유지하되(교차 시냅스 보존) `GET /api/fly/connectome?circuit=...`로 회로별
      필터링, HH 시뮬레이션도 명령이 속한 회로의 네트워크만 빌드하도록 스코핑해 실측
      속도도 개선(후각 ~6.7초, 시각 ~3.3초 vs 병합 네트워크 기준 10.2초). InstancedMesh는
      분리 후 최대 3,007개 규모에서도 여전히 불필요함을 브라우저 실측으로 재확인. z축
      오프셋 레이아웃 트릭은 페이지 분리로 더 이상 필요 없어져 제거. 나머지 VPN 타입에
      대한 커맨드/툴팁 확장은 문헌 근거가 뒷받침되는 만큼만 유지(의도적으로 보류). 자세한
      내용은
      [docs/10-fly-page-split-and-circuit-scoped-simulation.md](docs/10-fly-page-split-and-circuit-scoped-simulation.md)
      참고.
- [x] **4차 패스 완료 — 해부 영역 레이어 + 항법(나침반) 회로 추가** — 모든 `/fly/*`
      페이지에 실제 초파리 뇌 신경총(neuropil) 이름 라벨(촉각엽/버섯체/시엽/타원체 등,
      Ito et al. 2014 명명법)을 뉴런 클러스터 위에 반투명 영역으로 얹어 배경지식 없이도
      각 클러스터가 어느 뇌 영역인지 알 수 있게 함(on/off 토글 가능, 새 백엔드 필드
      불필요 — 기존 `categories_ko`로 프론트엔드에서 그룹핑). 세 번째 회로로 중심복합체
      헤딩/나침반 회로(`/fly/navigation`)를 추가 — ER(고리뉴런)/RING(EPG·PEN·PEG·Delta7
      나침반 링)/PFN(헤딩-목표 통합)/PFL(조향 출력), **총 896뉴런·39,964시냅스**.
      `EPG_L4`/`EPG_R4`/`EPG_R6`/`EPG_L2` 4개 헤딩 커맨드는 실제 EPG→PFL 시냅스 중
      가중치가 큰 것을 선정(문헌: Hulse et al. 2021, Rayshubskiy et al. 2020). 회로별
      페이지 분리·시뮬레이션 스코핑 구조를 그대로 재사용해 세 번째 회로도 다른 두
      회로의 성능에 영향을 주지 않음. 자세한 내용은
      [docs/11-fly-anatomy-regions-and-navigation-circuit.md](docs/11-fly-anatomy-regions-and-navigation-circuit.md)
      참고.
- [x] **5차 패스 완료 — 겉모습→감각기관→신경계 다이브인 연출** — 후각/시각
      페이지에 v1 스타일 슬라이더를 추가해 더듬이/겹눈(실측 스캔 아님, 도식적
      근사로 명시) → 촉각엽/시엽 진입부(흐르는 입자 연출) → 기존 신경망 뷰로
      점진적으로 파고드는 연출 구현(항법 페이지는 외부 감각기관이 없어 적용
      대상에서 제외). 부수적으로 "해부 영역 숨기기" 버튼이 뉴런/시냅스 개수
      텍스트와 겹치던 위치 버그와, `/fly/*` 페이지 최초 진입 시 캔버스 첫
      프레임이 그려지지 않던 버그(모든 회로 페이지에 영향)를 함께 수정. 자세한
      내용은 [docs/12-fly-dive-in-reveal.md](docs/12-fly-dive-in-reveal.md) 참고.

## v3: 인간 (Homo sapiens) — 커넥톰 · 게놈 1차 패스

인간은 웜/초파리와 달리 **뇌 전체를 뉴런 단위로 재구성한 지도가 존재하지 않는다**
(860억 뉴런 전체 EM 재구성은 기술적으로 불가능) — 그래서 실재하는 서로 다른
데이터를 섞지 않고 각각 별도 페이지로 정직하게 제공한다.

- [x] **1차 패스 완료** — `/human`(랜딩) → `/human/connectome`(거시/미시 선택) →
      `/human/connectome/macro`(Schaefer 400 파셀레이션 시각 네트워크, 실측 HCP
      확산MRI 연결성, 61개 영역·465개 실제 연결) / `/human/connectome/micro`
      (H01 인간 측두엽 실제 EM 재구성 샘플, 실제 뉴런 104개·4.1만 다운샘플링
      포인트) / `/human/genome`(hg38 실제 염색체 이데오그램 위에 GO 기능주석
      기반 신경계 유전자 511개 배치, 기능 주석 있음/미확인(가설) 마우스오버
      구분 + BDNF 활동의존적 발현 경로 명령→캐스케이드 시뮬레이션). 자세한
      내용·데이터 출처·한계는
      [docs/13-human-connectome-and-genome.md](docs/13-human-connectome-and-genome.md)
      참고.
- [ ] H01 시냅스 연결 벡터화(현재는 뉴런 형태만, Avro 샤드 파싱 필요)
- [ ] 게놈 기능별 필터 확장(다른 GO 카테고리)
- [ ] 거시 커넥톰에 Limbic 등 다른 네트워크 추가 — H01의 실제 측두엽 위치와
      더 가까운 네트워크를 추가하면 "거시 영역 클릭 → 그 영역의 실제 미시
      샘플"이라는 조합도 가능해짐

## 로컬 실행

### Docker Compose (권장)

```bash
docker compose up --build
```

- 프론트엔드: http://localhost:3000
- 백엔드: http://localhost:8000 (Swagger 문서: http://localhost:8000/docs)

### 개별 실행 (Docker 없이)

```bash
# 백엔드
cd backend
python -m venv .venv
./.venv/Scripts/pip install -r requirements.txt   # Windows
uvicorn app.main:app --reload

# 프론트엔드 (별도 터미널)
cd frontend
pnpm install
pnpm dev
```

`frontend/.env.local`에서 `NEXT_PUBLIC_API_URL` / `NEXT_PUBLIC_WS_URL`을 백엔드 주소로 설정하세요
(기본값: `http://localhost:8000` / `ws://localhost:8000`).

## 테스트

```bash
cd backend && ./.venv/Scripts/python -m pytest
cd frontend && pnpm build
```
