# Connectome data sources (vendored)

These two files are the real C. elegans (hermaphrodite) connectivity dataset
used to build `backend/app/data/celegans_connectome.json` via
`backend/scripts/build_connectome_dataset.py`. They are vendored (checked into
the repo) rather than fetched at build/run time, so the dataset is reproducible
offline.

## `herm_full_edgelist.csv`

- Source: [openworm/CElegansNeuroML](https://github.com/openworm/CElegansNeuroML/blob/master/herm_full_edgelist.csv)
  (fetched 2026-09-15 from the `master` branch)
- Content: every synaptic edge in the hermaphrodite connectome — 7,378 rows,
  columns `Source,Target,Weight,Type` (`Type` is `chemical` or `electrical`,
  `Weight` is EM-reconstructed synapse count between that pair).
- Underlying science: Varshney et al. 2011 / Cook et al. 2019 whole-animal EM
  reconstruction, as curated by the OpenWorm project for its `c302` neural
  model. Nodes include all 300 connected neurons plus body wall muscles
  (`dBWML*`/`dBWMR*`/`vBWML*`/`vBWMR*`), pharyngeal muscles/cells (`pm*`,
  `mc*`, `sph`), vulval/uterine muscles (`vm*`/`um*`), and gut/epidermis
  (`intestine`, `hyp`, `anal`, `intL`/`intR`).

## `owmeta_neuron_muscle_info.json`

- Source: [openworm/c302 `c302/data/owmeta_cache.json`](https://github.com/openworm/c302/blob/master/c302/data/owmeta_cache.json)
  (fetched 2026-09-15 from the `master` branch), renamed here for clarity.
- Content: per-neuron (`neuron_info`, 302 entries) classification (`sensory`
  / `interneuron` / `motor`, possibly more than one) and known
  neurotransmitter(s), exported from the [owmeta](https://owmeta.org/) C.
  elegans knowledge base. Also includes `muscle_info` (95 body wall muscles),
  not currently used — see the build script for why (naming scheme doesn't
  match the edge list's muscle names, so we treat edge-list muscle nodes as
  generic effectors instead of cross-referencing this).

## `celegans_neuron_soma_positions.json`

- Source: derived from [openworm/CElegansNeuroML `CElegans/generatedMorphML/*.morph.xml`](https://github.com/openworm/CElegansNeuroML/tree/master/CElegans/generatedMorphML)
  (302 files, one per neuron, fetched 2026-09-15 from the `master` branch).
  Extracted with a one-off script (not checked in — trivial to reproduce: for
  each `<NAME>.morph.xml`, take the first `<segment>`'s `<proximal>` x/y/z,
  which is that neuron's soma/cell-body position) into this single JSON
  (`{neuron_name: {x, y, z}}`, units: micrometres).
- Content: **real EM-reconstructed 3D soma coordinates** for all 302 neurons —
  this is the actual per-cell morphology data OpenWorm's NeuroML model is
  built from, not a computed layout. Verified 2026-09-15: every one of the
  302 neuron names in `celegans_connectome.json` has an exact-match entry
  here (no name normalization needed — this source already uses the same
  naming convention as `owmeta_neuron_muscle_info.json`).
- **Axis meaning** (verified by inspecting known head/tail neurons): `y` is
  the anterior-posterior (head-to-tail) body axis, spanning roughly -312 to
  +410 µm (~722 µm total — head interneurons like AVAL cluster near -270,
  tail neurons like PLML near +410). `x` and `z` are the two cross-sectional
  axes (left-right, dorsal-ventral), each spanning only ~50-125 µm, matching
  the worm's actual thin, elongated body plan (~14:1 length-to-diameter).
- Does **not** include effector (muscle/gut/epidermis) positions — no
  equivalent per-cell morphology file exists in this source for them. See
  `build_connectome_dataset.py` for how effector positions are derived
  instead (anchored to nearby real neuron coordinates plus known relative
  anatomy, e.g. vulval muscles placed at HSNL/HSNR's real y-position).
- The specimen behind this EM reconstruction was presumably mounted straight
  for imaging, not in a live crawling S-posture — the frontend applies a
  cosmetic sinusoidal bend to all positions for a recognizable worm
  silhouette (see `frontend/src/features/connectome-viewer/lib/body-pose.ts`);
  that bend is a rendering choice, not part of this real data.

## `wbbt_anatomy_ontology.obo`

- Source: [WormBase Gross Anatomy Ontology (WBbt)](http://obofoundry.org/ontology/wbbt.html),
  fetched 2026-09-15 via its OBO Foundry PURL (`purl.obolibrary.org/obo/wbbt.obo`),
  `data-version: releases/2025-08-19`. License: CC-BY 4.0. 1.6 MB, ~7,200 terms
  covering all C. elegans gross anatomy, not just neurons.
- Content: for each anatomy term (e.g. `AVA`, `AVAL`, `I3 neuron`), an English
  `def:` (a citable definition, often quoting the original EM reconstruction
  literature) and `is_a:` parent terms (functional/positional categories —
  e.g. `AVA` is_a `command interneuron`; `ASH` is_a `chemosensory neuron`,
  `nociceptor neuron`; `HSN` is_a `motor neuron`, `serotonergic neuron`).
  Some terms also carry a WormAtlas individual-neuron-page link.
- **Coverage verified 2026-09-15**: all 302 neurons in the dataset resolve to
  a `def:` (zero missing). Lookup tries several name variants per neuron
  (`resolve_neuron_ontology` in the build script) because the ontology names
  single/unpaired pharyngeal neurons as e.g. `"I3 neuron"` rather than bare
  `"I3"`, and because individual-cell terms (e.g. `AVAL`) often have a richer
  definition than their class-level term (`AVA`) but don't always carry their
  own `is_a` tags — the build script merges categories across every matching
  name variant rather than stopping at the first hit, so as not to under-report.
  Only `CANL`/`CANR` (the same two edge-list-isolated neurons noted above)
  lack `is_a` category tags in this source.
- `def:` text is stored and shown **verbatim in English**, not translated —
  translating a cited scientific definition risks introducing an error the
  source doesn't have. `is_a:` category labels (a much smaller, controlled
  vocabulary — see `CATEGORY_LABEL_KO` in the build script) are translated to
  Korean for the UI, since mistranslating "motor neuron" -> "운동뉴런" carries
  essentially no risk.
- This is a separate, independent thing from the ~55-class hand-authored
  Korean one-liners in `frontend/.../lib/neuron-info.ts` — those remain a
  bonus layer on top of this real per-neuron ontology data, not a
  replacement for it.

## What's still a placeholder / simplified after this import

- Two neurons (`CANL`, `CANR`) have zero edges in the edge list (no curated
  synapses at all) and so appear as isolated nodes.
- The edge list has a handful of numbering mismatches with `owmeta`
  (`VA1` vs `VA01`, etc.) — `normalize_numeric_suffix()` resolves these by
  zero-padding before matching; verified this leaves no neuron-named node
  unmatched.
- **446 of 7,378 edges (~6%) are dropped**: every edge whose *source* is a
  non-neuron cell (muscle-to-muscle gap junctions, intestine self-coupling,
  pharyngeal marginal-cell coupling, etc.) — i.e. effector-to-effector
  electrical spread. This build only keeps neuron-sourced edges, matching the
  app's neuron -> synapse -> effector command pipeline; it does not model
  muscle sheet electrical propagation. The kept 6,933 edges are exactly the
  neuron -> neuron and neuron -> effector connections.

## docs/47 추가: 시냅스 극성 예측

- `fenyves2020_S1_Data.xlsx` -- Fenyves, Szilágyi, Vassy, Sőti & Csermely 2020, PLOS Comput Biol
  16:e1007974, S1 Data (`https://linkgroup.hu/docs/S1_Data.xlsx`). `scripts/build_synapse_signs.py`가
  연결별 'Predicted polarity' 열을 그대로 `app/data/celegans_synapse_signs.json`으로 옮긴다
  (가상 웜 폐루프 전용 `sign_model="receptor_predicted"`).
