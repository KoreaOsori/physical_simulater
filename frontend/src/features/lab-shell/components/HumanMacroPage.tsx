"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";

import { DISORDER_HIGHLIGHT_COLOR, HumanMacroCanvas, type RegionOverride } from "@/features/connectome-viewer/components/HumanMacroCanvas";
import { DiveRevealSlider } from "@/features/connectome-viewer/components/DiveRevealSlider";
import { humanDiveStageLabel } from "@/features/connectome-viewer/lib/human-dive-stages";
import { LOBE_COLOR, LOBE_LABEL_KO, lobeForAnatomicalLabel, type Lobe } from "@/features/connectome-viewer/lib/human-lobes";
import { ChatPanel } from "@/features/human-chat/components/ChatPanel";
import { fetchHumanMacroConnectome } from "@/shared/lib/api-client";
import type { DisorderAssociation, MacroConnectome } from "@/types/human";

const NETWORK_LABELS: Record<string, string> = {
  Vis: "시각 (Vis)",
  SomMot: "체성감각/운동 (SomMot)",
  DorsAttn: "배측 주의 (DorsAttn)",
  SalVentAttn: "복측 주의/현출성 (SalVentAttn)",
  Limbic: "변연계 (Limbic)",
  Cont: "집행제어 (Cont)",
  Default: "디폴트모드/기억 (Default)",
};

const ANATOMY_LOBES: Lobe[] = ["frontal", "parietal", "temporal", "occipital"];

/** Static exploration page — unlike the fly circuit pages, there's no
 * command/simulation here (a group-consensus MRI connectivity matrix isn't
 * something you "stimulate"), so no store/event-log/playback machinery is
 * needed — just fetch-and-render. The dive-in reveal (겉모습→뇌 조직→신경계)
 * and network switch (Vis/Limbic) are local UI state only. 보기 모드
 * (docs/33)는 네트워크 스위치와 나란히 놓인 별개의 토글로, 4대엽 스위치 +
 * 엽별 질환 패널을 켠다 — 같은 400개 영역·같은 3D 캔버스를 다른 축으로
 * 다시 묶어서 보여주는 것뿐이라 별도 페이지/라우트를 만들지 않았다. */
export function HumanMacroPage() {
  const [connectome, setConnectome] = useState<MacroConnectome | null>(null);
  const [activeNetwork, setActiveNetwork] = useState("Vis");
  const [diveProgress, setDiveProgress] = useState(0);
  const [selectedDisorder, setSelectedDisorder] = useState<DisorderAssociation | null>(null);
  const [chatHighlightedRegionIds, setChatHighlightedRegionIds] = useState<string[]>([]);
  const [activeLobes, setActiveLobes] = useState<Lobe[]>([]);
  // 보기 모드(docs/33): 네트워크 스위치와 별개로, 4대엽 스위치 + 엽별 질환
  // 패널을 켜고 끌 수 있는 토글. anatomyLobe는 그 스위치 UI/질환 패널
  // 그룹핑 전용 단일 선택값 -- 챗봇이 여러 엽을 동시에 켤 수 있는
  // activeLobes(배열)와는 별개로 두되, 버튼을 누르면 activeLobes도 같이
  // 갱신해 3D 하이라이트가 실제로 따라오게 한다.
  const [viewMode, setViewMode] = useState<"network" | "anatomy">("network");
  const [anatomyLobe, setAnatomyLobe] = useState<Lobe>("frontal");

  useEffect(() => {
    fetchHumanMacroConnectome()
      .then(setConnectome)
      .catch((error: unknown) => console.error("Failed to load human macro connectome", error));
  }, []);

  // 보기 모드에 따라 "지금 화면에 실제로 보이는 것"의 정의 자체가 다르다
  // (네트워크 모드=activeNetwork 소속, 해부학 모드=anatomyLobe 소속) --
  // 상단 영역/연결 카운트와 챗봇에 보내는 visibleRegionIds 둘 다 여기 맞춰
  // 갱신해야, 해부학 모드에서도 옛 네트워크 값이 그대로 남아있지 않는다.
  const { visibleRegionCount, visibleEdgeCount, visibleRegionIds } = useMemo(() => {
    if (!connectome) return { visibleRegionCount: 0, visibleEdgeCount: 0, visibleRegionIds: [] as string[] };
    const regions =
      viewMode === "network"
        ? connectome.regions.filter((r) => r.network === activeNetwork)
        : connectome.regions.filter((r) => lobeForAnatomicalLabel(r.anatomical_label) === anatomyLobe);
    const ids = new Set(regions.map((r) => r.id));
    const edges = connectome.edges.filter((e) => ids.has(e.a) && ids.has(e.b));
    return { visibleRegionCount: regions.length, visibleEdgeCount: edges.length, visibleRegionIds: [...ids] };
  }, [connectome, activeNetwork, viewMode, anatomyLobe]);

  // Single map feeding HumanMacroCanvas's additive coloring: disorder
  // selection + chat-cited regions both use the SAME flat red sphere
  // ("these regions are collectively implicated", docs/21's convention) --
  // deliberately a different semantic, color AND marker shape from a lobe
  // request, which colors each lobe's regions distinctly as a facet-cut
  // marker (network vs. anatomy are genuinely different classifications of
  // the same regions, see docs/30's "네트워크 vs 해부학" section) rather
  // than lumping them into one highlight look.
  //
  // 실제 버그(docs/33): 엽 색칠 루프가 나중에 돌면서 같은 region id에
  // 무조건 colors.set()을 덮어써서, 선택한 질환의 영역이 마침 지금 보는
  // 엽 안에 있으면(흔한 경우 -- 예: 베르니케 실어증은 측두엽 안에 있음)
  // 질환 강조색이 조용히 사라지고 엽 색으로 바뀌어버렸다. 그래서
  // "해부학 모드에서 질환을 클릭해도 안 보이고, 네트워크 모드로 가야만
  // 보이는" 문제가 실제로 있었다. 고침: 엽 멤버십(모양)과 색 우선순위를
  // 분리 -- 색은 항상 질환 인용이 엽 배경보다 우선하고(클릭이라는 더
  // 명시적인 행동이니까), 모양(다면체 여부)은 별도로 "지금 활성 엽에도
  // 속하는지"를 그대로 반영해서 두 관계가 동시에 보이게 한다.
  const additiveRegionColors = useMemo(() => {
    const colors = new Map<string, RegionOverride>();
    const lobeMemberIds = new Set<string>();
    if (activeLobes.length > 0 && connectome) {
      const lobeSet = new Set(activeLobes);
      for (const region of connectome.regions) {
        const lobe = lobeForAnatomicalLabel(region.anatomical_label);
        if (lobe && lobeSet.has(lobe)) {
          lobeMemberIds.add(region.id);
          colors.set(region.id, { color: LOBE_COLOR[lobe], kind: "lobe", isLobeMember: true });
        }
      }
    }
    for (const id of selectedDisorder?.region_ids ?? []) {
      colors.set(id, { color: DISORDER_HIGHLIGHT_COLOR, kind: "disorder", isLobeMember: lobeMemberIds.has(id) });
    }
    for (const id of chatHighlightedRegionIds) {
      colors.set(id, { color: DISORDER_HIGHLIGHT_COLOR, kind: "disorder", isLobeMember: lobeMemberIds.has(id) });
    }
    return colors;
  }, [selectedDisorder, chatHighlightedRegionIds, activeLobes, connectome]);

  // Focal syndromes are grouped by whichever network most of their real
  // affected regions belong to (primary_network, a majority vote computed
  // backend-side) — switching the active network swaps which focal list
  // shows. Complex/multi-network conditions have no single honest network
  // home, so they're always shown in a separate "공통" section regardless
  // of activeNetwork.
  const focalForActiveNetwork = connectome?.known_disorders.filter((d) => d.category === "focal" && d.primary_network === activeNetwork) ?? [];
  // Same idea, one level down (docs/33): primary_lobe is the same
  // majority-vote grouping over the real classical 4-lobe mapping instead
  // of the Yeo-7 network -- lets 보기 모드="anatomy" show "이 엽에 실제로
  // 주로 걸쳐 있는 질환" the same way the network switch already does.
  const focalForActiveLobe = connectome?.known_disorders.filter((d) => d.category === "focal" && d.primary_lobe === anatomyLobe) ?? [];
  const complexDisorders = connectome?.known_disorders.filter((d) => d.category === "complex") ?? [];

  const selectLobe = (lobe: Lobe) => {
    setAnatomyLobe(lobe);
    setActiveLobes([lobe]);
  };

  const renderDisorderItem = (d: DisorderAssociation) => {
    const isSelected = selectedDisorder?.name === d.name;
    return (
      <div key={d.name} className="disorder-item">
        <button type="button" aria-pressed={isSelected} onClick={() => setSelectedDisorder(isSelected ? null : d)}>
          {d.name}
        </button>
        {isSelected && <p className="disorder-detail">{d.description}</p>}
      </div>
    );
  };

  return (
    <main className="lab-shell">
      <header className="topbar">
        <div className="brand">
          <b>∿</b> 신경 / <strong>인간 연구소</strong>
          <i>β</i>
        </div>
        <div className="specimen-title">
          <span>표본</span>
          <strong>인간 / 거시 커넥톰</strong>
          <em>Schaefer 400 · HCP 확산MRI 연결성</em>
        </div>
        <div className="top-status">
          <Link href="/human/connectome" className="species-switch">
            ↑ 커넥톰 목록
          </Link>
        </div>
      </header>
      <section className="viewport">
        <div className="view-meta">
          <span>모델 뷰 / 3D · 드래그로 회전, 스크롤로 확대</span>
          <span>{connectome ? `영역 ${visibleRegionCount} · 연결 ${visibleEdgeCount}` : "로딩 중"}</span>
        </div>
        {connectome && connectome.networks.length > 0 && (
          <div className="human-side-panel">
            <div className="network-switch">
              <button
                type="button"
                aria-pressed={viewMode === "network"}
                onClick={() => {
                  setViewMode("network");
                  setActiveLobes([]);
                }}
              >
                네트워크
              </button>
              <button
                type="button"
                aria-pressed={viewMode === "anatomy"}
                onClick={() => {
                  setViewMode("anatomy");
                  selectLobe(anatomyLobe);
                }}
              >
                해부학(4대엽)
              </button>
            </div>
            {viewMode === "network" ? (
              <div className="network-switch">
                {connectome.networks.map((net) => (
                  <button
                    key={net}
                    type="button"
                    aria-pressed={activeNetwork === net}
                    onClick={() => setActiveNetwork(net)}
                  >
                    {NETWORK_LABELS[net] ?? net}
                  </button>
                ))}
              </div>
            ) : (
              <div className="network-switch">
                {ANATOMY_LOBES.map((lobe) => (
                  <button key={lobe} type="button" aria-pressed={anatomyLobe === lobe} onClick={() => selectLobe(lobe)}>
                    {LOBE_LABEL_KO[lobe]}
                  </button>
                ))}
              </div>
            )}
            {viewMode === "network" ? (
              focalForActiveNetwork.length > 0 && (
                <div className="disorder-group">
                  <small>{NETWORK_LABELS[activeNetwork] ?? activeNetwork} · 국소 증후군</small>
                  {focalForActiveNetwork.map(renderDisorderItem)}
                </div>
              )
            ) : (
              focalForActiveLobe.length > 0 && (
                <div className="disorder-group">
                  <small>{LOBE_LABEL_KO[anatomyLobe]} · 국소 증후군</small>
                  {focalForActiveLobe.map(renderDisorderItem)}
                </div>
              )
            )}
            {complexDisorders.length > 0 && (
              <div className="disorder-group">
                <small>공통 · 복합·다발성 질환</small>
                {complexDisorders.map(renderDisorderItem)}
              </div>
            )}
          </div>
        )}
        <DiveRevealSlider
          progress={diveProgress}
          onChange={setDiveProgress}
          stageLabel={humanDiveStageLabel(diveProgress)}
          stops={["겉모습", "뇌 조직", "신경계"]}
        />
        <ChatPanel
          activeNetwork={activeNetwork}
          visibleRegionIds={visibleRegionIds}
          selectedDisorderName={selectedDisorder?.name ?? null}
          onHighlightRegions={setChatHighlightedRegionIds}
          onShowLobes={setActiveLobes}
        />
        <div className="scanlines" />
        <HumanMacroCanvas
          connectome={connectome}
          activeNetwork={activeNetwork}
          diveProgress={diveProgress}
          additiveRegionColors={additiveRegionColors}
          showNetworkBaseline={viewMode === "network"}
        />
        <div className="legend">
          <span><i style={{ background: "#e0b48c" }} />두피(T1w 임계 등위면, MNI 템플릿)</span>
          <span><i style={{ background: "#ff6b81" }} />회백질(신경계, 실제 회백질 확률 등위면)</span>
          {viewMode === "network" && (
            <>
              <span><i style={{ background: "#75cce9" }} />{NETWORK_LABELS[activeNetwork] ?? activeNetwork} 영역(파셀)</span>
              <span><i style={{ background: "#9fe27a" }} />실측 구조 연결(합의 이진 SC)</span>
            </>
          )}
          {selectedDisorder && <span><i style={{ background: "#ff3b3b" }} />{selectedDisorder.name} 관련 부위</span>}
          {chatHighlightedRegionIds.length > 0 && (
            <span><i style={{ background: "#ff3b3b" }} />챗봇 요청으로 강조된 영역</span>
          )}
          {activeLobes.map((lobe) => (
            <span key={lobe}><i style={{ background: LOBE_COLOR[lobe] }} />◆ {LOBE_LABEL_KO[lobe]}(해부학적 구분, AAL · 다면체 마커로 네트워크 점과 구분)</span>
          ))}
        </div>
      </section>
    </main>
  );
}
