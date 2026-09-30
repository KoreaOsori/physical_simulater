"use client";

import { useMemo, useState } from "react";

import { colorForStain } from "@/features/genome-viewer/lib/cytoband-colors";
import type { CytoBand, Gene } from "@/types/human";

const CHROM_ORDER = [...Array.from({ length: 22 }, (_, i) => String(i + 1)), "X", "Y"];

const BAR_WIDTH = 14;
const COLUMN_WIDTH = 34;
const MAX_BAR_HEIGHT = 420;
const TOP_MARGIN = 10;

interface HumanChromosomeIdeogramProps {
  cytobands: CytoBand[];
  genes: Gene[];
  activeGeneIds: Set<string>;
  onHoverGene: (gene: Gene | null, x: number, y: number) => void;
}

/** Real hg38 cytogenetic ideogram — 24 chromosomes drawn at their real
 * relative physical length (see backend build_human_dataset.py), each band
 * colored by its real UCSC stain classification. Genes plotted at the real
 * cytoband their `map_location` matches to (position_fraction — null for
 * ~4% of genes this project couldn't match to a specific band, which are
 * simply not plotted rather than guessed). Confidence coloring: green =
 * real NCBI functional annotation on file, orange = "미확인(가설)" — sparse
 * or no annotation, an honest reflection of the source data's own gaps, not
 * an invented hypothesis. */
export function HumanChromosomeIdeogram({ cytobands, genes, activeGeneIds, onHoverGene }: HumanChromosomeIdeogramProps) {
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  const byChrom = useMemo(() => {
    const map = new Map<string, CytoBand[]>();
    for (const b of cytobands) {
      if (!map.has(b.chromosome)) map.set(b.chromosome, []);
      map.get(b.chromosome)!.push(b);
    }
    return map;
  }, [cytobands]);

  const genesByChrom = useMemo(() => {
    const map = new Map<string, Gene[]>();
    for (const g of genes) {
      if (g.position_fraction === null) continue;
      if (!map.has(g.chromosome)) map.set(g.chromosome, []);
      map.get(g.chromosome)!.push(g);
    }
    return map;
  }, [genes]);

  const maxChromLength = useMemo(
    () => Math.max(...cytobands.map((b) => b.end)),
    [cytobands],
  );

  const totalWidth = CHROM_ORDER.length * COLUMN_WIDTH;
  const totalHeight = MAX_BAR_HEIGHT + TOP_MARGIN * 2 + 20;

  return (
    <svg width={totalWidth} height={totalHeight} className="chromosome-ideogram">
      {CHROM_ORDER.map((chrom, i) => {
        const bands = byChrom.get(chrom) ?? [];
        if (bands.length === 0) return null;
        const chromLength = Math.max(...bands.map((b) => b.end));
        const barHeight = (chromLength / maxChromLength) * MAX_BAR_HEIGHT;
        const x = i * COLUMN_WIDTH;
        const chromGenes = genesByChrom.get(chrom) ?? [];

        return (
          <g key={chrom} transform={`translate(${x}, ${TOP_MARGIN})`}>
            {bands.map((b) => {
              const y0 = (b.start / chromLength) * barHeight;
              const y1 = (b.end / chromLength) * barHeight;
              return (
                <rect
                  key={`${b.chromosome}-${b.band}`}
                  x={0}
                  y={y0}
                  width={BAR_WIDTH}
                  height={Math.max(y1 - y0, 0.5)}
                  fill={colorForStain(b.stain)}
                />
              );
            })}
            <rect x={0} y={0} width={BAR_WIDTH} height={barHeight} fill="none" stroke="#0a1611" strokeWidth={0.6} />
            <text x={BAR_WIDTH / 2} y={barHeight + 14} textAnchor="middle" className="ideogram-chrom-label">
              {chrom}
            </text>
            {chromGenes.map((g) => {
              const y = (g.position_fraction as number) * barHeight;
              const active = activeGeneIds.has(g.id);
              const color = g.confidence === "annotated" ? "#baff71" : "#ffb86b";
              return (
                <circle
                  key={g.id}
                  cx={BAR_WIDTH + 4}
                  cy={y}
                  r={active ? 3.4 : hoveredId === g.id ? 3 : 1.8}
                  fill={color}
                  opacity={active ? 1 : 0.85}
                  onMouseEnter={(e) => {
                    setHoveredId(g.id);
                    onHoverGene(g, e.clientX, e.clientY);
                  }}
                  onMouseMove={(e) => onHoverGene(g, e.clientX, e.clientY)}
                  onMouseLeave={() => {
                    setHoveredId(null);
                    onHoverGene(null, 0, 0);
                  }}
                />
              );
            })}
          </g>
        );
      })}
    </svg>
  );
}
