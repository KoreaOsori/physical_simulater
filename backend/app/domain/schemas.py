"""Domain models shared across the API: connectome structure and simulation events.

These mirror the frontend types in `frontend/src/types/connectome.ts` — keep both
sides in sync when a field changes.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

CircuitName = Literal["olfactory", "visual", "navigation"]
"""Known Drosophila circuit-subset tags (see build_drosophila_dataset.py). A
plain Literal rather than an Enum so adding a future circuit subset only
touches this line plus the dataset/route wiring, not a shared enum other
species also import."""


class NeuronType(str, Enum):
    SENSORY = "sensory"
    INTER = "inter"
    MOTOR = "motor"
    UNKNOWN = "unknown"  # not curated with a role in the source data


class SynapseType(str, Enum):
    CHEMICAL = "chemical"
    ELECTRICAL = "electrical"  # gap junction


class Neurotransmitter(str, Enum):
    ACETYLCHOLINE = "acetylcholine"
    GABA = "gaba"
    GLUTAMATE = "glutamate"
    DOPAMINE = "dopamine"
    SEROTONIN = "serotonin"
    OCTOPAMINE = "octopamine"
    TYRAMINE = "tyramine"
    ELECTRICAL = "electrical"  # gap-junction synapses carry no chemical transmitter
    UNKNOWN = "unknown"  # not curated in the source data (common for command interneurons)


class EffectorType(str, Enum):
    MUSCLE = "muscle"
    GUT = "gut"
    EPIDERMIS = "epidermis"
    OTHER = "other"


class Position3D(BaseModel):
    x: float
    y: float
    z: float


class Neuron(BaseModel):
    id: str
    name: str
    type: NeuronType
    position: Position3D
    neurotransmitter: Neurotransmitter
    description_en: str | None = Field(
        default=None, description="Definition from WormBase's anatomy ontology (WBbt), English, verbatim."
    )
    categories_ko: list[str] = Field(
        default_factory=list, description="Korean labels for this neuron's WBbt functional/positional categories."
    )
    wormatlas_url: str | None = Field(default=None, description="Link to this neuron's WormAtlas page, if known.")
    cell_type: str | None = Field(
        default=None,
        description="Raw source cell-type name (e.g. hemibrain's `type` column, 'LC4'/'MBON01'/'KCab') for "
        "precise per-type lookups. Null for datasets that don't carry one (e.g. C. elegans, where `id` "
        "already encodes the class).",
    )
    circuit: CircuitName | None = Field(
        default=None,
        description="Which circuit subset this neuron belongs to within a multi-subset dataset (see "
        "build_drosophila_dataset.py) — lets a single merged dataset be filtered per subset "
        "(GET /api/fly/connectome?circuit=...) without a second dataset file. Null for single-subset "
        "datasets (e.g. C. elegans).",
    )


class Effector(BaseModel):
    """A non-neuron synapse endpoint: muscle, gut, or epidermis cell. Real
    connectome edge lists include these as synapse/NMJ targets alongside
    neurons (see app/data/sources/SOURCES.md)."""

    id: str
    name: str
    kind: EffectorType
    position: Position3D


class Synapse(BaseModel):
    id: str
    pre: str = Field(description="Source neuron id")
    post: str = Field(description="Target neuron or effector id")
    type: SynapseType
    neurotransmitter: Neurotransmitter
    weight: float = Field(ge=0, description="EM-reconstructed synapse count between this pair")


class Connectome(BaseModel):
    organism: str
    neuron_count_total: int = Field(description="Number of neurons in `neurons` (302 for the full C. elegans set).")
    effector_count_total: int = Field(description="Number of muscle/gut/epidermis cells in `effectors`.")
    is_placeholder: bool = Field(
        description="True while `neurons`/`synapses` hold a demo subset rather than the full dataset."
    )
    neurons: list[Neuron]
    effectors: list[Effector]
    synapses: list[Synapse]


class SimulationStage(str, Enum):
    COMMAND = "command"
    SYNAPSE = "synapse"
    NEUROTRANSMITTER = "neurotransmitter"
    MUSCLE = "muscle"
    MOVEMENT = "movement"


class SimulationEvent(BaseModel):
    t_ms: float = Field(description="Milliseconds since the command was issued")
    stage: SimulationStage
    source: str | None = None
    target: str | None = None
    neurotransmitter: Neurotransmitter | None = None
    message: str


class Direction(str, Enum):
    FORWARD = "forward"
    REVERSE = "reverse"
    LEFT = "left"
    RIGHT = "right"
    STOP = "stop"
    FEED = "feed"
    DEFECATE = "defecate"
    REPRODUCE = "reproduce"


class ClassicAblation(BaseModel):
    """One real laser-ablation study, resolved against this dataset's actual
    neuron ids -- see app/data/celegans_classic_ablations.py and
    docs/26-worm-classic-ablation-behavior.md."""

    name: str
    category: str = Field(description="e.g. 'locomotion', 'sensory', 'reproductive' -- free-text grouping, not an enum (small curated list).")
    description: str
    neuron_ids: list[str] = Field(description="This dataset's actual neuron ids the cited study ablated.")


class CommandRequest(BaseModel):
    direction: Direction
    silenced_neuron_ids: list[str] | None = Field(
        default=None,
        description="Approximates a classic laser-ablation experiment by silencing these neurons' outputs for this command only (hh_model.py) — see docs/26-worm-classic-ablation-behavior.md. Ignored by the rule-based fallback engine.",
    )


class CommandResponse(BaseModel):
    direction: Direction
    events: list[SimulationEvent]
    habituation_level: float = Field(
        default=0.0,
        description="0 (naive) to hh_model._MAX_HABITUATION -- how depressed this direction's stimulated neuron's own output synapses are right now, from repeated recent stimulation (real phenomenon: Rankin, Beck & Chiba 1990's tap-withdrawal habituation; recovers over time if unstimulated). Always 0 for directions with no HH pathway or when the rule-based fallback engine is used. See docs/29-worm-habituation-plasticity.md.",
    )


class OdorCommand(str, Enum):
    """A stimulus command for the Drosophila olfactory-circuit subset (v2).

    Named directly after the real antennal-lobe glomerulus it stimulates
    (see app/data/sources/drosophila/SOURCES.md) rather than an invented
    odor name — we only know what glomerulus fires, not what real-world
    smell a user would associate with it, except DA1 which is well-cited in
    the literature as the male pheromone (cVA) glomerulus.
    """

    DA1 = "DA1"  # pheromone (cVA) glomerulus — Kurtovic et al. 2007
    DL2D = "DL2d"
    VM5D = "VM5d"
    DA2 = "DA2"


class VisualCommand(str, Enum):
    """A stimulus command for the Drosophila visual-circuit subset (v2 phase
    2) — real hemibrain lobula/lobula-plate visual projection neuron (VPN)
    types, each with a direct real synapse (weight >= 3, see
    app/simulation/fly_engine.py's `_VISUAL_PATHWAYS`) onto a descending
    neuron (DN). Picked as the four VPN types with the largest total real
    synaptic weight into the DN layer (see
    app/data/sources/drosophila/SOURCES.md), which also happen to be the
    best-published looming/escape and object-detection channels in the
    literature — not an invented list.
    """

    LC4 = "LC4"  # looming/escape, feeds the Giant Fiber pathway — e.g. von Reyn et al. 2014
    LC6 = "LC6"  # looming/escape, feeds the Giant Fiber pathway — e.g. von Reyn et al. 2017
    LPLC2 = "LPLC2"  # binocular looming detector, direct Giant Fiber input — Ache et al. 2019
    LC9 = "LC9"  # small moving object / visual pursuit — e.g. Klapoetke et al. 2017


class HeadingCommand(str, Enum):
    """A stimulus command for the Drosophila central-complex (navigation)
    circuit subset (v2 phase 4) — real hemibrain EPG "compass" neurons, each
    named after the real protocerebral-bridge wedge it occupies (hemibrain's
    own `instance` naming, e.g. "EPG(PB08)_L4"). Each has a direct real
    synapse (weight >= 3, see app/simulation/fly_engine.py's `_NAV_PATHWAYS`)
    onto a PFL steering-output neuron — the best-published central-complex
    output cell type (Rayshubskiy et al. 2020; Mussells Pires et al. 2024).
    Picked as four wedges (mixing left/right and PFL1/2/3) with the largest
    real EPG->PFL synaptic weight (see
    app/data/sources/drosophila/SOURCES.md) — not an invented list.
    """

    EPG_L4 = "EPG_L4"  # -> PFL2, weight 78
    EPG_R4 = "EPG_R4"  # -> PFL2, weight 50
    EPG_R6 = "EPG_R6"  # -> PFL3, weight 48
    EPG_L2 = "EPG_L2"  # -> PFL1, weight 40


FlyStimulus = OdorCommand | VisualCommand | HeadingCommand


class FlyCommandRequest(BaseModel):
    stimulus: FlyStimulus


class FlyCommandResponse(BaseModel):
    stimulus: FlyStimulus
    events: list[SimulationEvent]


# --- Human (v3): macro-scale region connectome, a real micro-scale EM
# sample, and a nervous-system gene map. See app/data/sources/human/SOURCES.md
# for why these are three separate, honestly-scoped datasets rather than one
# unified "human connectome" — no whole-brain neuron-level human connectome
# exists (unlike C. elegans/Drosophila).


class BrainRegion(BaseModel):
    """One parcel of a real macro-scale brain atlas (Schaefer2018 400-parcel,
    7-network) — a statistical region, not a single traced cell. `position`
    is a 3D-scene-framed version of this parcel's real MNI centroid;
    `mni_coordinate_mm` is the same real point, unscaled, for anyone who
    wants to check it against an atlas or paper (docs/32)."""

    id: str
    name: str = Field(description="Atlas ROI name, e.g. '7Networks_LH_Vis_9'.")
    network: str = Field(description="Yeo-7 functional network this parcel belongs to, e.g. 'Vis'.")
    position: Position3D = Field(
        description="Real MNI centroid, recentered and uniformly scaled for 3D scene framing — preserves real "
        "relative geometry (not a schematic layout) but is NOT directly comparable to a published MNI coordinate. "
        "Use `mni_coordinate_mm` for that."
    )
    mni_coordinate_mm: Position3D = Field(
        description="The literal, unscaled real MNI152 centroid in millimeters (x=R, y=A, z=S — the order MNI "
        "coordinates are conventionally reported in), exactly as vendored from the source atlas — this is what to "
        "check against a paper or atlas viewer, not `position`."
    )
    anatomical_label: str | None = Field(
        default=None,
        description="Real AAL atlas region name (Tzourio-Mazoyer et al. 2002) whose voxel this parcel's real MNI "
        "centroid falls in/nearest to — e.g. 'Calcarine_L'. A coordinate lookup, not a claim that the Schaefer "
        "parcel and the AAL region are the same shape (see SOURCES.md). Null if no AAL-labeled tissue was found "
        "nearby (honestly left unset, not guessed).",
    )
    anatomical_note: str | None = Field(
        default=None,
        description="Short general-neuroanatomy functional note for `anatomical_label` (e.g. 'primary visual "
        "cortex') — well-established textbook fact keyed off the AAL name, not a per-parcel measurement.",
    )


class RegionEdge(BaseModel):
    """A real HCP-derived structural connection between two atlas parcels.
    `weight` is 0/1 (binary group-consensus presence, see SOURCES.md) —
    not a synapse count or streamline count."""

    a: str
    b: str
    weight: float = Field(ge=0)


class AnatomyMeshLayer(BaseModel):
    """One triangle-mesh isosurface layer for the macro dive-in reveal
    (겉모습→조직→신경계). Vertices come from real MNI152NLin2009cAsym template
    volumes (marching cubes over T1w/brain-mask/gray-matter-probability
    voxels), not an authored/schematic shape — see SOURCES.md's "두개골/뇌
    표면 메시" section for the population-average caveat. `positions` is a
    flat [x0,y0,z0,x1,y1,z1,...] array already in this scene's coordinate
    frame (same centering/scale as `BrainRegion.position`); `indices` is a
    flat triangle index array."""

    positions: list[float]
    indices: list[int]
    vertex_count: int
    triangle_count: int


class HeadAnatomy(BaseModel):
    skin: AnatomyMeshLayer = Field(description="Outer head/scalp isosurface (T1w intensity threshold).")
    brain: AnatomyMeshLayer = Field(description="Brain envelope isosurface (binary brain mask).")
    gray_matter: AnatomyMeshLayer = Field(description="Cortical gray-matter isosurface — where cortical neuron cell bodies actually sit.")
    source: str = Field(description="Provenance note for these three layers (see SOURCES.md).")
    h01_region_hint: Position3D = Field(
        description="Real MNI centroid of the Limbic/TempPole parcels (temporal pole) — the closest macro-atlas "
        "neighborhood to where the H01 micro sample was physically taken. NOT a registered coordinate for the H01 "
        "sample itself (H01 has no MNI registration) — an honest approximate neighborhood marker only."
    )


class DisorderAssociation(BaseModel):
    """A classic, textbook-level lesion-symptom association (e.g. Broca's
    aphasia, Phineas Gage's orbitofrontal injury) — real established
    clinical neurology, not this project's own diagnosis. `region_ids` are
    resolved from real `anatomical_label` matches actually present in this
    dataset (see human_anatomical_labels.py's `resolve_disorders`), never a
    guess at which parcel "should" be involved."""

    name: str
    category: Literal["focal", "complex"] = Field(
        description="'focal' = classic single/few-region lesion syndrome. 'complex' = real condition with "
        "well-documented multi-network involvement and a genuinely multifactorial cause — kept visually separate "
        "from focal syndromes so a long region list is never mistaken for 'the cause'."
    )
    primary_network: str | None = Field(
        description="For 'focal' entries: the real Yeo-7 network the majority of its region_ids belong to (a plain "
        "vote over real network membership) — lets the UI group it under the one network it mostly lives in. "
        "Always null for 'complex' entries, which by definition have no single honest network home."
    )
    primary_lobe: str | None = Field(
        default=None,
        description="Same majority-vote logic as primary_network, one level down: the real classical 4-lobe "
        "(frontal/parietal/temporal/occipital, human_lobes.py) the majority of its region_ids belong to. Null for "
        "'complex' entries (same reasoning as primary_network) AND for any 'focal' entry whose regions all fall "
        "outside the 4 classical lobes (e.g. insula/cingulate-only entries) — never forced into a lobe it doesn't "
        "really belong to.",
    )
    description: str = Field(description="Includes an explicit caveat that real causes/course are more complex.")
    anatomical_labels: list[str] = Field(description="Real AAL base names classically implicated (e.g. ['Fusiform']).")
    region_ids: list[str] = Field(description="This dataset's actual region ids whose anatomical_label matches.")


class MacroConnectome(BaseModel):
    networks: list[str]
    region_count_total: int
    regions: list[BrainRegion]
    edges: list[RegionEdge]
    anatomy: HeadAnatomy
    known_disorders: list[DisorderAssociation] = Field(default_factory=list)


class MicroNeuronPoint(BaseModel):
    """One (decimated) real skeleton point from the H01 EM reconstruction —
    see SOURCES.md for the 100:1 downsampling. `neuron_id` groups points
    belonging to the same one of the 104 real proofread neurons."""

    neuron_id: str
    position: Position3D
    radius: float


class SynapseRole(str, Enum):
    AXON = "AXON"  # this neuron is the presynaptic/sending side of the contact
    DENDRITE = "DENDRITE"  # this neuron is the postsynaptic/receiving side


class MicroSynapseContact(BaseModel):
    """One real synaptic contact point from the H01 synapse-export database
    (see SOURCES.md's "실제 시냅스 접촉점" section) where at least one side is
    one of the 104 real proofread neurons. `partner_is_proofread` is included
    for completeness but real data showed it's essentially always false — see
    SOURCES.md for why (the 104 weren't selected as an interconnected
    circuit). No excitatory/inhibitory label: this export's numeric type
    fields aren't a verified E/I classification (see fetch_h01_synapses.py)."""

    neuron_id: str
    role: SynapseRole
    partner_neuron_id: str
    partner_is_proofread: bool
    position: Position3D
    confidence: float | None = None


class MicroConnectomeSample(BaseModel):
    source_region: str = Field(description="Real anatomical origin of this sample (temporal cortex) — see SOURCES.md.")
    neuron_count_total: int
    point_count_total: int
    points: list[MicroNeuronPoint]
    synapse_count_total: int
    synapses: list[MicroSynapseContact]


class GeneConfidence(str, Enum):
    ANNOTATED = "annotated"  # has a real NCBI description + protein-coding
    HYPOTHETICAL = "hypothetical"  # sparse/no functional annotation in the source data — see SOURCES.md


class Gene(BaseModel):
    id: str
    symbol: str
    chromosome: str
    map_location: str = Field(description="Real cytogenetic band, e.g. '11p14.1' — from NCBI gene_info.")
    description: str | None = None
    type_of_gene: str
    go_tags: list[str] = Field(default_factory=list, description="Real GO-term-derived functional tags (see SOURCES.md).")
    confidence: GeneConfidence
    position_fraction: float | None = Field(
        default=None,
        description="0-1 position along this gene's chromosome, computed from the midpoint of the real UCSC "
        "cytoband matching `map_location` (see build_human_dataset.py). Null if no matching band was found.",
    )


class CytoBand(BaseModel):
    """One real cytogenetic band from the UCSC hg38 ideogram — used to draw
    chromosomes at their real relative physical proportions."""

    chromosome: str
    start: int
    end: int
    band: str
    stain: str


class HumanGenome(BaseModel):
    gene_count_total: int
    genes: list[Gene]
    cytobands: list[CytoBand]


class GenePathwayCommand(str, Enum):
    """A stimulus for the human-genome activity-dependent expression cascade
    demo — see app/simulation/human_genome_engine.py and SOURCES.md's BDNF
    (Tao et al. 1998; Greenberg et al. 2009) and Arc/Arg3.1 (Bramham et al.
    2008) sections. Each command added here needs a real, well-cited pathway
    behind it — not just any gene sequence."""

    BDNF_ACTIVATION = "BDNF_ACTIVATION"
    ARC_PLASTICITY_ACTIVATION = "ARC_PLASTICITY_ACTIVATION"


class GenomeCommandRequest(BaseModel):
    stimulus: GenePathwayCommand


class GenomeCommandResponse(BaseModel):
    stimulus: GenePathwayCommand
    events: list[SimulationEvent]


class SpeciesDatasetScale(BaseModel):
    """One species' entry in GET /api/compare/summary. Two deliberately
    separate kinds of numbers, never merged into one: what THIS PROJECT'S
    dataset actually contains (`dataset_*`, always traceable to a real file
    this repo ships) vs. the real organism's biological scale for context
    (`real_world_*`, always cited, nullable when no defensible single number
    exists). See docs/23-cross-species-scale-comparison.md."""

    species_id: str
    common_name_ko: str
    scientific_name: str
    is_dataset_complete: bool = Field(
        description="True only when dataset_neuron_count essentially equals the species' real total (true for C. elegans; false for Drosophila's 3-circuit subset and human, which has no per-neuron dataset at all)."
    )
    dataset_neuron_count: int | None = Field(description="Neurons actually present in this dataset's neuron-level data, if any.")
    dataset_synapse_count: int | None = Field(description="Synapses actually present in this dataset's neuron-level data, if any.")
    dataset_region_count: int | None = Field(default=None, description="Region/parcel count, for datasets that are region-level rather than neuron-level (human macro).")
    dataset_note: str = Field(description="What the dataset_* numbers above do and don't cover, in prose.")
    real_world_neuron_count: int | None = Field(description="A citable estimate of the real organism's total neuron count, for scale context only.")
    real_world_neuron_count_note: str = Field(description="Citation and any hedging on how precise/uncertain that estimate is.")


class CompareSummary(BaseModel):
    species: list[SpeciesDatasetScale]


class HumanChatRequest(BaseModel):
    """See docs/30-human-macro-chat-panel.md. `active_network`/
    `visible_region_ids`/`selected_disorder_name` describe what's actually
    on screen right now -- the chat's retrieval starts from this, not a
    free search over the whole dataset."""

    message: str = Field(min_length=1, max_length=500)
    active_network: str | None = None
    visible_region_ids: list[str] = Field(default_factory=list)
    selected_disorder_name: str | None = None


class HumanChatResponse(BaseModel):
    answer: str
    used_source_ids: list[str] = Field(
        description="Which real DB entries (region/disorder/gene, see human_chat_context.ChatCorpusDoc.id) the answer actually drew on -- shown to the user so the answer stays checkable against the underlying data, not just asserted."
    )
    highlighted_region_ids: list[str] = Field(
        default_factory=list,
        description="Regions to highlight in ONE color (the disorder-panel's red, see docs/21) -- derived only from used_source_ids' region/disorder citations, e.g. a disorder's whole real affected-region set. Deliberately does NOT include lobe-view regions -- see requested_lobes.",
    )
    requested_lobes: list[str] = Field(
        default_factory=list,
        description="Real lobe keys ('frontal'/'parietal'/'temporal'/'occipital') detected in the message, e.g. from '전두엽 보여줘'. The frontend already has every region's real anatomical_label loaded, so it resolves this into actual region ids AND assigns each lobe its own distinct color client-side (app/data/human_lobes.py's LOBE_LABEL_KO keys are the same strings) -- kept separate from highlighted_region_ids because a whole-lobe view is semantically 'distinct areas, distinct colors', not 'these regions are collectively implicated' like a disorder highlight.",
    )
