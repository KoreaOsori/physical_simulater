"""Real AAL region -> classical 4-lobe (전두엽/두정엽/측두엽/후두엽) mapping,
for the human macro connectome chat panel's "전두엽 보여줘" style requests
(docs/30-human-macro-chat-panel.md).

This is a DIFFERENT axis than the Yeo-7 functional networks
(app/data/human_macro_connectome.json's `network` field, see docs/13/19-21)
-- a Yeo network like Default Mode spans multiple lobes, and a single lobe
contains regions from multiple Yeo networks. Folk neuroanatomy ("the 4
lobes") and functional-connectivity parcellation are genuinely orthogonal
classifications, not a filter of one another.

Source: the classical lobe grouping of AAL's own 116 regions, as used in
Tzourio-Mazoyer et al. 2002 (NeuroImage, the original AAL atlas paper) and
reproduced in derivative AAL literature (e.g. Rolls, Huang, Lin, Feng &
Joliot 2020's AAL3 update) -- AAL itself categorizes regions into
Frontal/Parietal/Temporal/Occipital/Insula/Limbic/SCGM(subcortical gray
matter)/Cerebellum, not just the 4 classical lobes. Only the 38 AAL base
names that actually appear in this project's dataset (real AAL matches from
docs/19's coordinate lookup, checked directly against
human_macro_connectome.json) are listed below -- not the full 116, since
the rest were never matched to a real region here.

Honestly flagged: two regions sit at classical lobe boundaries and are
assigned by majority convention in AAL derivative literature, not
anatomical certainty --
- Paracentral_Lobule: straddles the central sulcus (motor/frontal anterior
  part, sensory/parietal posterior part); grouped under Frontal here,
  matching Tzourio-Mazoyer et al. 2002's own table.
- Rolandic_Oper (Rolandic operculum): frontal opercular tissue adjacent to
  the Sylvian fissure; grouped under Frontal.

Regions NOT part of the classical 4 lobes in AAL's own scheme (Insula,
Cingulum_*, ParaHippocampal -- AAL's "Limbic" category) are honestly left
out of the 4-lobe grouping rather than forced into one -- see LOBE_OTHER.
"""

from __future__ import annotations

LOBE_FRONTAL = "frontal"
LOBE_PARIETAL = "parietal"
LOBE_TEMPORAL = "temporal"
LOBE_OCCIPITAL = "occipital"
LOBE_OTHER = "other"  # real AAL region, but not part of the classical 4 lobes

LOBE_LABEL_KO = {
    LOBE_FRONTAL: "전두엽",
    LOBE_PARIETAL: "두정엽",
    LOBE_TEMPORAL: "측두엽",
    LOBE_OCCIPITAL: "후두엽",
    LOBE_OTHER: "4대엽 분류 밖(변연계/뇌섬엽 등)",
}

# AAL base name (anatomical_label with the trailing _L/_R stripped, same
# convention as backend/scripts/human_anatomical_labels.py's _base_name) ->
# lobe. Only the 38 base names actually present in this dataset.
_AAL_BASE_TO_LOBE: dict[str, str] = {
    # Frontal
    "Frontal_Inf_Oper": LOBE_FRONTAL,
    "Frontal_Inf_Orb": LOBE_FRONTAL,
    "Frontal_Inf_Tri": LOBE_FRONTAL,
    "Frontal_Med_Orb": LOBE_FRONTAL,
    "Frontal_Mid": LOBE_FRONTAL,
    "Frontal_Mid_Orb": LOBE_FRONTAL,
    "Frontal_Sup": LOBE_FRONTAL,
    "Frontal_Sup_Medial": LOBE_FRONTAL,
    "Frontal_Sup_Orb": LOBE_FRONTAL,
    "Precentral": LOBE_FRONTAL,
    "Rectus": LOBE_FRONTAL,
    "Rolandic_Oper": LOBE_FRONTAL,
    "Supp_Motor_Area": LOBE_FRONTAL,
    "Paracentral_Lobule": LOBE_FRONTAL,
    # Parietal
    "Parietal_Inf": LOBE_PARIETAL,
    "Parietal_Sup": LOBE_PARIETAL,
    "Postcentral": LOBE_PARIETAL,
    "Angular": LOBE_PARIETAL,
    "SupraMarginal": LOBE_PARIETAL,
    "Precuneus": LOBE_PARIETAL,
    # Temporal
    "Temporal_Inf": LOBE_TEMPORAL,
    "Temporal_Mid": LOBE_TEMPORAL,
    "Temporal_Pole_Mid": LOBE_TEMPORAL,
    "Temporal_Pole_Sup": LOBE_TEMPORAL,
    "Temporal_Sup": LOBE_TEMPORAL,
    "Fusiform": LOBE_TEMPORAL,
    "Heschl": LOBE_TEMPORAL,
    # Occipital
    "Calcarine": LOBE_OCCIPITAL,
    "Cuneus": LOBE_OCCIPITAL,
    "Lingual": LOBE_OCCIPITAL,
    "Occipital_Inf": LOBE_OCCIPITAL,
    "Occipital_Mid": LOBE_OCCIPITAL,
    "Occipital_Sup": LOBE_OCCIPITAL,
    # Not part of the classical 4 lobes (AAL's own Insula/Limbic categories)
    "Insula": LOBE_OTHER,
    "Cingulum_Ant": LOBE_OTHER,
    "Cingulum_Mid": LOBE_OTHER,
    "Cingulum_Post": LOBE_OTHER,
    "ParaHippocampal": LOBE_OTHER,
}


def _base_name(aal_label: str) -> str:
    """Strips a trailing _L/_R hemisphere suffix -- same rule as
    scripts/human_anatomical_labels.py's own _base_name()."""
    if aal_label.endswith("_L") or aal_label.endswith("_R"):
        return aal_label[:-2]
    return aal_label


def lobe_for_anatomical_label(anatomical_label: str | None) -> str | None:
    """None when there's no real AAL label to look up, or it's a real label
    this table doesn't (yet) cover -- never guessed."""
    if not anatomical_label:
        return None
    return _AAL_BASE_TO_LOBE.get(_base_name(anatomical_label))
