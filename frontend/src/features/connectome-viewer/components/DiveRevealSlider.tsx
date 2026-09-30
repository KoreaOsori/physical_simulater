"use client";

interface DiveRevealSliderProps {
  progress: number;
  onChange: (progress: number) => void;
  stageLabel: string;
  /** The three stop labels shown under the track, outer-to-inner. */
  stops: [string, string, string];
}

/** Shared "dive-in" reveal control — v1's LayerControlPanel, v2's per-circuit
 * fly dive slider, and the human macro/micro pages all drag through the same
 * three named stages (겉모습→조직→신경계) on one 0-100 slider; only the
 * labels differ per page. See dive-reveal.ts for the opacity math this
 * `progress` value drives. */
export function DiveRevealSlider({ progress, onChange, stageLabel, stops }: DiveRevealSliderProps) {
  return (
    <div className="layer-panel">
      <small>해부 단계</small>
      <strong>{stageLabel}</strong>
      <input
        type="range"
        min={0}
        max={100}
        step={1}
        value={Math.round(progress * 100)}
        onChange={(e) => onChange(Number(e.target.value) / 100)}
        aria-label="해부 단계 슬라이더"
      />
      <div className="layer-panel-stops">
        {stops.map((s) => (
          <span key={s}>{s}</span>
        ))}
      </div>
    </div>
  );
}
