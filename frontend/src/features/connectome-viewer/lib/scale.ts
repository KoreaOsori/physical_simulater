/**
 * Scene-units <-> real-world micrometre conversion for the worm scene.
 *
 * NOT an independent choice — this MUST stay equal to `_UM_TO_SCENE` in
 * `backend/scripts/build_connectome_dataset.py` (currently `1 / 60.0`),
 * which is what actually placed the real EM soma positions
 * (`celegans_neuron_soma_positions.json`, micrometres) into scene units in
 * the first place: real AP span ~722 um -> ~12 scene units. If that backend
 * constant ever changes, this one must change with it (see
 * `backend/tests/test_hh_model.py`'s scale-constant test, which pins the
 * backend side so a drift here would show up as a failing cross-check
 * documented in docs/22-worm-locomotion-real-speed-grounding.md).
 *
 * This is what lets any on-screen displacement (e.g. the RFT locomotion
 * solver's output, see rft-locomotion.ts) be converted into a real velocity
 * (um/s) and checked against literature crawling-speed measurements
 * (Fang-Yen et al. 2010, PNAS 107:20323: ~200-400 um/s) — something that was
 * previously impossible because the scene had no explicit real-unit anchor
 * on the frontend side, even though the backend already had one.
 */
export const SCENE_UNITS_TO_UM = 60;
