"use client";

import { activeLayerLabel } from "@/features/connectome-viewer/lib/layer-reveal";
import { useSimulationStore } from "@/store/simulation-store";

/**
 * Top-left popup, styled after OpenWorm's "peel away" body visualization:
 * drag the slider to progressively fade the outer cuticle and reveal
 * muscle/gut/epidermis, then the nervous system underneath.
 */
export function LayerControlPanel() {
  const layerReveal = useSimulationStore((s) => s.layerReveal);
  const setLayerReveal = useSimulationStore((s) => s.setLayerReveal);

  return (
    <div className="layer-panel">
      <small>해부 레이어</small>
      <strong>{activeLayerLabel(layerReveal)}</strong>
      <input
        type="range"
        min={0}
        max={100}
        step={1}
        value={layerReveal}
        onChange={(e) => setLayerReveal(Number(e.target.value))}
        aria-label="해부 레이어 슬라이더"
      />
      <div className="layer-panel-stops">
        <span>겉모습</span>
        <span>근육/조직</span>
        <span>신경계</span>
      </div>
    </div>
  );
}
