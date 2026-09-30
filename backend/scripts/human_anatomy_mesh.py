"""Builds the three dive-in-reveal mesh layers (겉모습→조직→신경계: skin/brain
envelope/gray matter) for the human macro connectome scene, from the real
MNI152NLin2009cAsym template volumes vendored in
app/data/sources/human/mni_template/ (templateflow, public domain — see
SOURCES.md's "두개골/뇌 표면 메시" section for exact provenance and the
population-average-template caveat).

Marching-cubes isosurfaces over real registered voxel data, not authored or
schematic geometry — but also not one specific person's skull scan: this is a
smoothed group-average template, so edges are soft compared to an individual
scan (documented, not hidden).

Needs nibabel + scikit-image (see scripts/requirements-build.txt) — a
one-off build-time dependency, not part of the app's runtime requirements.txt.
"""

from __future__ import annotations

from pathlib import Path

import nibabel as nib
import numpy as np
from skimage import measure

MNI_DIR = Path(__file__).resolve().parent.parent / "app" / "data" / "sources" / "human" / "mni_template"

T1W_PATH = MNI_DIR / "tpl-MNI152NLin2009cAsym_res-02_T1w.nii.gz"
BRAIN_MASK_PATH = MNI_DIR / "tpl-MNI152NLin2009cAsym_res-02_desc-brain_mask.nii.gz"
GM_PROBSEG_PATH = MNI_DIR / "tpl-MNI152NLin2009cAsym_res-02_label-GM_probseg.nii.gz"

# marching-cubes voxel stride — keeps triangle counts small enough to ship as
# plain JSON (no binary mesh format in this project's stack yet). 3 keeps the
# combined payload under ~1.5MB while these are translucent reveal shells,
# not a precision-viewing target.
_STEP_SIZE = 3
# T1w intensity threshold approximating the skin/air boundary. This template
# is a nonlinear-registration group average, so its outer edge is blurred
# across several voxels rather than a crisp boundary (see SOURCES.md) — this
# level was picked by inspecting where the isosurface's real-world bounding
# box (~190x228x190mm) matches a plausible adult head size, not derived from
# a documented spec.
_SKIN_LEVEL = 1200.0
_BRAIN_LEVEL = 0.5  # binary mask, so any level in (0, 1) gives the same surface
_GM_LEVEL = 0.4  # gray-matter probability threshold

SOURCE_NOTE = (
    "MNI152NLin2009cAsym (templateflow, res-02/2mm, public domain) — 실제 등록된 "
    "MRI 그룹 평균 템플릿에서 marching cubes로 뽑아낸 등위면(skin: T1w 강도 임계, "
    "brain: 이진 뇌 마스크, gray_matter: 회백질 확률 임계). 개인 두개골 스캔이 "
    "아니라 여러 명을 정합·평균한 템플릿이라 가장자리가 실제 개인 스캔보다 "
    "부드럽게 뭉개져 있음 — 위치·비율은 실제 MNI 좌표계 기준."
)


def compute_reference_frame(scene_span: float) -> tuple[float, float, float, float]:
    """Real MNI-space center (R,A,S mm) and one uniform scale factor, derived
    from the brain mask's own real bounding box. This is the single
    coordinate frame shared by every region (any network) and every anatomy
    mesh layer in the macro scene — a region and the gray-matter shell around
    it are never independently recentered/rescaled."""
    img = nib.load(BRAIN_MASK_PATH)
    data = np.asarray(img.dataobj, dtype=np.float64)
    aff = img.affine
    idx = np.argwhere(data > 0.5)
    world = (aff[:3, :3] @ idx.T).T + aff[:3, 3]
    mins, maxs = world.min(axis=0), world.max(axis=0)
    cr, ca, cs = (mins[0] + maxs[0]) / 2, (mins[1] + maxs[1]) / 2, (mins[2] + maxs[2]) / 2
    span = float(np.max(maxs - mins))
    scale = scene_span / span
    return cr, ca, cs, scale


def _to_scene(world: np.ndarray, frame: tuple[float, float, float, float]) -> np.ndarray:
    cr, ca, cs, scale = frame
    r, a, s = world[:, 0], world[:, 1], world[:, 2]
    # Same MNI->three.js remap as build_macro(): S->y (up), A->z (depth), R->x.
    x = (r - cr) * scale
    y = (s - cs) * scale
    z = (a - ca) * scale
    return np.stack([x, y, z], axis=1)


def _isosurface_layer(path: Path, level: float, frame: tuple[float, float, float, float]) -> dict:
    img = nib.load(path)
    data = np.asarray(img.dataobj, dtype=np.float64)
    aff = img.affine
    verts, faces, _normals, _values = measure.marching_cubes(data, level=level, step_size=_STEP_SIZE)
    world = (aff[:3, :3] @ verts.T).T + aff[:3, 3]
    scene = _to_scene(world, frame)
    positions = [round(float(c), 4) for row in scene for c in row]
    indices = [int(i) for tri in faces for i in tri]
    return {
        "positions": positions,
        "indices": indices,
        "vertex_count": len(scene),
        "triangle_count": len(faces),
    }


def build_head_anatomy(scene_span: float, h01_hint_world: tuple[float, float, float]) -> tuple[dict, tuple[float, float, float, float]]:
    frame = compute_reference_frame(scene_span)
    skin = _isosurface_layer(T1W_PATH, _SKIN_LEVEL, frame)
    brain = _isosurface_layer(BRAIN_MASK_PATH, _BRAIN_LEVEL, frame)
    gray_matter = _isosurface_layer(GM_PROBSEG_PATH, _GM_LEVEL, frame)
    hint_scene = _to_scene(np.array([h01_hint_world]), frame)[0]
    anatomy = {
        "skin": skin,
        "brain": brain,
        "gray_matter": gray_matter,
        "source": SOURCE_NOTE,
        "h01_region_hint": {"x": round(float(hint_scene[0]), 4), "y": round(float(hint_scene[1]), 4), "z": round(float(hint_scene[2]), 4)},
    }
    print(
        f"anatomy mesh: skin {skin['vertex_count']}v/{skin['triangle_count']}t, "
        f"brain {brain['vertex_count']}v/{brain['triangle_count']}t, "
        f"gray_matter {gray_matter['vertex_count']}v/{gray_matter['triangle_count']}t"
    )
    return anatomy, frame
