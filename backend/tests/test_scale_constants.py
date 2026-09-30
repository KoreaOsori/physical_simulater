"""Cross-checks the backend's um<->scene-unit conversion factor
(`_UM_TO_SCENE` in scripts/build_connectome_dataset.py) against its frontend
mirror (`SCENE_UNITS_TO_UM` in
frontend/src/features/connectome-viewer/lib/scale.ts). The two live in
separate runtimes (Python build script vs. TypeScript app) with no shared
source of truth, so nothing else would catch one changing without the other
-- see docs/22-worm-locomotion-real-speed-grounding.md."""

import re
from pathlib import Path

from scripts.build_connectome_dataset import _UM_TO_SCENE

_FRONTEND_SCALE_FILE = (
    Path(__file__).resolve().parent.parent.parent
    / "frontend"
    / "src"
    / "features"
    / "connectome-viewer"
    / "lib"
    / "scale.ts"
)


def test_frontend_scene_units_to_um_matches_backend_um_to_scene() -> None:
    text = _FRONTEND_SCALE_FILE.read_text(encoding="utf-8")
    match = re.search(r"SCENE_UNITS_TO_UM\s*=\s*([\d.]+)", text)
    assert match is not None, "frontend scale.ts constant not found -- did it move/get renamed?"
    frontend_scene_units_to_um = float(match.group(1))

    backend_scene_units_to_um = 1 / _UM_TO_SCENE
    assert frontend_scene_units_to_um == backend_scene_units_to_um
