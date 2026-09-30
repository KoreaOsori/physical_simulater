"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";

import { HumanGenomeEventLog } from "@/features/event-log/components/HumanGenomeEventLog";
import { HumanChromosomeIdeogram } from "@/features/genome-viewer/components/HumanChromosomeIdeogram";
import { HumanGenomeCommandBar } from "@/features/simulation-control/components/HumanGenomeCommandBar";
import { scheduleGenomePlayback } from "@/features/simulation-control/lib/genome-playback";
import { fetchHumanGenome } from "@/shared/lib/api-client";
import { openGenomePathwaySocket } from "@/shared/lib/ws-client";
import { useHumanGenomeStore } from "@/store/human-genome-store";
import type { Gene } from "@/types/human";

export function HumanGenomePage() {
  const genome = useHumanGenomeStore((s) => s.genome);
  const setGenome = useHumanGenomeStore((s) => s.setGenome);
  const setConnectionStatus = useHumanGenomeStore((s) => s.setConnectionStatus);
  const activeGeneIds = useHumanGenomeStore((s) => s.activeGeneIds);

  const [filter, setFilter] = useState("all");
  const [hovered, setHovered] = useState<{ gene: Gene; x: number; y: number } | null>(null);

  useEffect(() => {
    fetchHumanGenome()
      .then(setGenome)
      .catch((error: unknown) => console.error("Failed to load human genome", error));

    const close = openGenomePathwaySocket({
      onMessage: (message) => scheduleGenomePlayback(message.direction, message.events),
      onStatusChange: setConnectionStatus,
    });
    return close;
  }, [setGenome, setConnectionStatus]);

  const counts = useMemo(() => {
    const tags = ["nervous_system_development", "chemical_synaptic_transmission", "visual_perception"];
    const c: Record<string, number> = { all: genome?.genes.length ?? 0 };
    for (const tag of tags) c[tag] = 0;
    for (const g of genome?.genes ?? []) {
      for (const tag of tags) if (g.go_tags.includes(tag)) c[tag]++;
    }
    return c;
  }, [genome]);

  const filteredGenes = useMemo(() => {
    if (!genome) return [];
    if (filter === "all") return genome.genes;
    return genome.genes.filter((g) => g.go_tags.includes(filter));
  }, [genome, filter]);

  return (
    <main className="lab-shell">
      <header className="topbar">
        <div className="brand">
          <b>∿</b> 신경 / <strong>인간 연구소</strong>
          <i>β</i>
        </div>
        <div className="specimen-title">
          <span>표본</span>
          <strong>인간 / 신경계 유전자 지도</strong>
          <em>hg38 · GO 기능 주석 646개 유전자(신경계 511 + 시각 지각 135)</em>
        </div>
        <div className="top-status">
          <Link href="/human" className="species-switch">
            ↑ 인간 홈
          </Link>
        </div>
      </header>
      <section className="workspace-fly">
        <div className="viewport genome-viewport">
          <div className="view-meta">
            <span>염색체 이데오그램(hg38) · 마우스오버로 유전자 정보 확인</span>
            <span>{genome ? `유전자 ${filteredGenes.length}/${genome.gene_count_total}` : "로딩 중"}</span>
          </div>
          <div className="genome-scroll">
            {genome && (
              <HumanChromosomeIdeogram
                cytobands={genome.cytobands}
                genes={filteredGenes}
                activeGeneIds={activeGeneIds}
                onHoverGene={(gene, x, y) => setHovered(gene ? { gene, x, y } : null)}
              />
            )}
          </div>
          <div className="legend">
            <span><i style={{ background: "#baff71" }} />기능 주석 있음</span>
            <span><i style={{ background: "#ffb86b" }} />미확인(가설)</span>
          </div>
          {hovered && (
            <div className="neuron-tooltip gene-tooltip" style={{ left: hovered.x + 14, top: hovered.y + 14 }}>
              <strong>
                {hovered.gene.symbol}
                {hovered.gene.confidence === "hypothetical" && <em> · 미확인(가설)</em>}
              </strong>
              <p className="neuron-tooltip-meta">
                {hovered.gene.chromosome}번 염색체 · {hovered.gene.map_location} · {hovered.gene.type_of_gene}
              </p>
              <p className="neuron-tooltip-curated">
                {hovered.gene.description ?? "NCBI에 기능 설명이 등록되어 있지 않습니다 — 기능 불명·가설 단계."}
              </p>
              {hovered.gene.go_tags.length > 0 && (
                <p className="neuron-tooltip-degree">GO 태그: {hovered.gene.go_tags.join(", ")}</p>
              )}
            </div>
          )}
        </div>
        <HumanGenomeEventLog />
      </section>
      <HumanGenomeCommandBar filter={filter} onFilterChange={setFilter} counts={counts} />
    </main>
  );
}
