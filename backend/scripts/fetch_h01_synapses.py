"""One-off fetch: streams all 166 real H01 synapse-export Avro shards
(gs://h01-release/data/20210729/c3/synapses/exported/, ~33GB, ~166M records)
and keeps only the records that touch one of the 104 real proofread neurons
in app/data/sources/human/h01_micro_sample_points.csv.

Real finding from a 7-shard (~7M record, 4.2%) sample before running this
full pass: records where BOTH partners are among the 104 proofread neurons
are effectively zero (none found) — these 104 were hand-picked individually
across the tissue sample for morphological diversity, not as an
interconnected circuit, so direct neuron-to-neuron synapses between them
essentially don't exist. What DOES exist in real numbers: synapses where
ONE side is a real proofread neuron and the other is an unproofread/unnamed
segment (~3,663 in the 7-shard sample -> ~87,000 extrapolated across all 166
shards). This script gets the *exact* real set, not an extrapolation.

Coordinate note (verified empirically, see SOURCES.md): this export's
`location` x/y is in a FINER-resolution coordinate space than the proofread
skeletons' x/y — real matched records show `location.x/4` and `location.y/4`
land inside the corresponding neuron's real skeleton bounding box in 99.7%
of 1,197 sampled rows at zero margin (100% at a 500-unit margin, consistent
with a synapse sitting on the membrane surface rather than the centerline
skeleton trace). `location.z` needs no correction — it's already in the same
units as the skeleton z. This script writes RAW (uncorrected) x/y/z, matching
this project's convention of keeping vendored source data raw and applying
documented corrections in build_human_dataset.py, not here.

Field note (see SOURCES.md): this export's per-partner `type`/`subtype`
integers are NOT a verified excitatory/inhibitory classification — sampled
records show pre_synaptic_site.type constant at 1 and
post_synaptic_partner.type constant at 2 across every example checked, i.e.
these look like a pre/post role marker, not a neurotransmitter class. E/I
labels are a separate, differently-shaped H01 export
(`c3/synapses/precomputed`) this project isn't using. So the only honestly
usable per-synapse role signal here is `class_label` (AXON vs DENDRITE) on
whichever side is one of the 104 — i.e. "this neuron is the sending/axonal
side" vs "this neuron is the receiving/dendritic side" of that contact.

Usage (downloads ~33GB total, run once and keep the output):

    cd backend
    ./.venv/Scripts/python -m pip install fastavro
    ./.venv/Scripts/python scripts/fetch_h01_synapses.py
"""

from __future__ import annotations

import csv
import io
import urllib.request
from pathlib import Path

import fastavro

SOURCES_DIR = Path(__file__).resolve().parent.parent / "app" / "data" / "sources" / "human"
PROOFREAD_POINTS_PATH = SOURCES_DIR / "h01_micro_sample_points.csv"
OUT_PATH = SOURCES_DIR / "h01_micro_sample_synapses.csv"

SHARD_COUNT = 166
BASE_URL = "https://storage.googleapis.com/h01-release/data/20210729/c3/synapses/exported/export{:012d}"


def _load_proofread_ids() -> set[int]:
    ids: set[int] = set()
    with PROOFREAD_POINTS_PATH.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            ids.add(int(row["neuron_id"]))
    return ids


def _iter_shard_records(shard_index: int):
    url = BASE_URL.format(shard_index)
    with urllib.request.urlopen(url, timeout=120) as resp:
        buf = io.BytesIO(resp.read())
    yield from fastavro.reader(buf)


def fetch() -> None:
    proofread_ids = _load_proofread_ids()
    print(f"matching against {len(proofread_ids)} real proofread neuron IDs")

    both_count = 0
    one_side_count = 0
    total_records = 0

    with OUT_PATH.open("w", newline="", encoding="utf-8") as out_f:
        writer = csv.writer(out_f)
        writer.writerow(
            [
                "neuron_id",
                "role",  # AXON (this neuron is presynaptic/sending) or DENDRITE (postsynaptic/receiving)
                "partner_neuron_id",  # the other side's neuron_id — NOT necessarily one of the 104
                "partner_is_proofread",  # true only if the partner is also one of the 104 (see module docstring: expected ~0)
                "x",
                "y",
                "z",
                "confidence",
            ]
        )

        for shard_index in range(SHARD_COUNT):
            shard_both = 0
            shard_matches = 0
            shard_total = 0
            for rec in _iter_shard_records(shard_index):
                shard_total += 1
                pre = rec["pre_synaptic_site"]
                post = rec["post_synaptic_partner"]
                pre_id = pre.get("neuron_id")
                post_id = post.get("neuron_id")
                pre_in = pre_id in proofread_ids
                post_in = post_id in proofread_ids
                if not pre_in and not post_in:
                    continue
                if pre_in and post_in:
                    shard_both += 1
                loc = rec["location"]
                if pre_in:
                    writer.writerow(
                        [pre_id, "AXON", post_id, post_in, loc["x"], loc["y"], loc["z"], rec.get("confidence")]
                    )
                    shard_matches += 1
                if post_in:
                    writer.writerow(
                        [post_id, "DENDRITE", pre_id, pre_in, loc["x"], loc["y"], loc["z"], rec.get("confidence")]
                    )
                    shard_matches += 1
            both_count += shard_both
            one_side_count += shard_matches
            total_records += shard_total
            print(
                f"shard {shard_index + 1}/{SHARD_COUNT}: {shard_total} records, "
                f"{shard_matches} matched rows written (both-proofread so far: {both_count})"
            )

    print(f"DONE. total records scanned: {total_records}, matched rows written: {one_side_count}, both-proofread total: {both_count}")
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    fetch()
