"""Retrieval corpus + lookup for the human macro connectome chat panel
(docs/30-human-macro-chat-panel.md, docs/31-human-chat-semantic-search.md).
DB-grounded only: every corpus entry is built directly from this project's
own already-cited data (region anatomical notes, disorder descriptions, gene
descriptions) -- nothing here is fetched from or generated about sources
outside this dataset.

Retrieval has three channels, unioned together (see `search_corpus` and
`semantic_search_corpus`):
1. Whatever the frontend says is currently visible on screen (active
   network / region ids / selected disorder).
2. A plain keyword match of region/disorder/gene names (and the eponym
   synonym table below) mentioned in the user's own message -- catches
   exact/near-exact name matches cheaply, no network call.
3. (docs/31, added after channel 2 alone was found live to miss paraphrased
   questions with no literal name overlap) Embedding-based semantic search
   over PRECOMPUTED corpus embeddings (`build_human_chat_embeddings.py`,
   `sources/human/human_chat_embeddings.json`) -- only the user's query is
   embedded at request time (one extra OpenAI call per message), corpus
   embeddings are a committed build artifact, never recomputed live. Best
   effort: any failure (missing file, API error) degrades to channels 1+2
   silently, never breaks the chat response.
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.data.human_data import get_genome, get_macro_connectome
from app.data.human_lobes import lobe_for_anatomical_label

logger = logging.getLogger(__name__)

MAX_CORPUS_DOCS_PER_REQUEST = 60

# Kept in sync with build_human_chat_embeddings.py -- a request-time query
# MUST be embedded with the same model/dimensions the corpus was built with,
# or cosine similarity is meaningless.
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 256
EMBEDDINGS_PATH = Path(__file__).resolve().parent / "sources" / "human" / "human_chat_embeddings.json"

# Empirically picked against real queries during development (see docs/31)
# -- low enough to catch genuine paraphrases, high enough to reject
# unrelated corpus docs a 256-dim small embedding model still ranks above 0.
SEMANTIC_SIMILARITY_THRESHOLD = 0.35
SEMANTIC_TOP_K = 8


@dataclass(frozen=True)
class ChatCorpusDoc:
    id: str
    text: str
    kind: str  # "region" | "disorder" | "gene"
    region_id: str | None  # set only for "region" docs -- lets the chat response highlight it back


@lru_cache
def _build_corpus() -> list[ChatCorpusDoc]:
    docs: list[ChatCorpusDoc] = []
    macro = get_macro_connectome()
    for region in macro.regions:
        if not region.anatomical_note:
            continue
        label = region.anatomical_label or region.name
        docs.append(
            ChatCorpusDoc(
                id=f"region:{region.id}",
                # No raw region id repeated inline in the body -- it already
                # lives in the doc's own "[region:<id>]" tag (see
                # _build_instructions), and repeating it as prose confused
                # the model into echoing the wrong id in used_source_ids
                # (caught in a real live check this session).
                text=f"{label} ({region.network} 네트워크): {region.anatomical_note}",
                kind="region",
                region_id=region.id,
            )
        )
    for disorder in macro.known_disorders:
        docs.append(
            ChatCorpusDoc(
                id=f"disorder:{disorder.name}",
                text=f"{disorder.name} ({'국소' if disorder.category == 'focal' else '복합'}): {disorder.description}",
                kind="disorder",
                region_id=None,
            )
        )
    genome = get_genome()
    for gene in genome.genes:
        if not gene.description:
            continue
        docs.append(
            ChatCorpusDoc(
                id=f"gene:{gene.symbol}",
                text=f"{gene.symbol} (염색체 {gene.map_location}): {gene.description}",
                kind="gene",
                region_id=None,
            )
        )
    return docs


def _region_doc_ids_by_region_id() -> dict[str, ChatCorpusDoc]:
    return {doc.region_id: doc for doc in _build_corpus() if doc.region_id}


def search_corpus(
    message: str,
    active_network: str | None,
    visible_region_ids: list[str],
    selected_disorder_name: str | None,
) -> list[ChatCorpusDoc]:
    """On-screen context first (what the frontend says is actually visible),
    then a plain substring keyword match of the message against every
    corpus doc's text -- catches region/disorder/gene names the user typed
    even if that item isn't currently on screen. Capped so the prompt sent
    to the model stays a reasonable size."""
    corpus = _build_corpus()
    selected: list[ChatCorpusDoc] = []
    seen_ids: set[str] = set()

    by_region = _region_doc_ids_by_region_id()
    for region_id in visible_region_ids:
        doc = by_region.get(region_id)
        if doc and doc.id not in seen_ids:
            selected.append(doc)
            seen_ids.add(doc.id)

    if selected_disorder_name:
        for doc in corpus:
            if doc.kind == "disorder" and doc.id == f"disorder:{selected_disorder_name}" and doc.id not in seen_ids:
                selected.append(doc)
                seen_ids.add(doc.id)

    message_lower = message.lower()
    if message_lower.strip():
        for doc in corpus:
            if len(selected) >= MAX_CORPUS_DOCS_PER_REQUEST:
                break
            if doc.id in seen_ids:
                continue
            # Cheap containment check against the doc's own leading label
            # (region/disorder/gene name), not a full-text scan -- avoids
            # matching on common Korean words inside long descriptions.
            label = doc.text.split(" (", 1)[0]
            if not label:
                continue
            label_lower = label.lower()
            # Real match found live: "Fusiform" typed by a user didn't match
            # the stored label "Fusiform_L" (hemisphere suffix) -- strip it,
            # and also check individual AAL_Name_Parts tokens (e.g. a query
            # saying just "Frontal" should still surface "Frontal_Sup_Orb_L")
            # rather than only a whole-label match.
            label_no_hemisphere = label_lower[:-2] if label_lower.endswith(("_l", "_r")) else label_lower
            tokens = [t for t in label_no_hemisphere.replace("_", " ").split(" ") if len(t) >= 4]
            if (
                label_lower in message_lower
                or label_no_hemisphere in message_lower
                or any(token in message_lower for token in tokens)
            ):
                selected.append(doc)
                seen_ids.add(doc.id)

    named_areas = detect_named_area_synonyms(message)
    if named_areas:
        wanted_bases = {base for synonym in named_areas for base in synonym.aal_bases}
        for doc in corpus:
            if len(selected) >= MAX_CORPUS_DOCS_PER_REQUEST:
                break
            if doc.id in seen_ids or doc.kind != "region":
                continue
            label = doc.text.split(" (", 1)[0]
            base = label[:-2] if label.endswith(("_L", "_R")) else label
            if base in wanted_bases:
                selected.append(doc)
                seen_ids.add(doc.id)

    return selected[:MAX_CORPUS_DOCS_PER_REQUEST]


_LOBE_KEYWORDS = {
    "전두엽": "frontal",
    "두정엽": "parietal",
    "측두엽": "temporal",
    "후두엽": "occipital",
}


@dataclass(frozen=True)
class NamedAreaSynonym:
    canonical_ko: str
    aal_bases: tuple[str, ...]


# Real eponymous/popular region names that don't appear anywhere in this
# dataset's AAL labels (the atlas uses purely descriptive gyrus names) but
# that people actually type -- a live user query for "베로니카"(a common
# mishearing/typo of 베르니케, Wernicke) turned up nothing and dead-ended.
# Mappings are real, cited neuroanatomy, not guesses:
# - Broca's area = pars triangularis + pars opercularis of the inferior
#   frontal gyrus (BA44/45), classically the dominant (usually left)
#   hemisphere (Neuroanatomy, Broca Area -- StatPearls/NCBI Bookshelf
#   NBK526096). Both hemispheres' parcels are surfaced since this dataset
#   has no per-person language-lateralization data to pick a side.
# - Wernicke's area = posterior superior temporal gyrus (BA22), dominant
#   hemisphere. AAL doesn't split anterior/posterior STG, so the whole
#   Temporal_Sup parcel is the closest real match.
_NAMED_AREA_SYNONYMS: dict[str, NamedAreaSynonym] = {
    "브로카": NamedAreaSynonym("브로카 영역", ("Frontal_Inf_Tri", "Frontal_Inf_Oper")),
    "broca": NamedAreaSynonym("브로카 영역", ("Frontal_Inf_Tri", "Frontal_Inf_Oper")),
    "베르니케": NamedAreaSynonym("베르니케 영역", ("Temporal_Sup",)),
    "베로니카": NamedAreaSynonym("베르니케 영역", ("Temporal_Sup",)),
    "wernicke": NamedAreaSynonym("베르니케 영역", ("Temporal_Sup",)),
}


def detect_named_area_synonyms(message: str) -> list[NamedAreaSynonym]:
    """Real eponyms mentioned in the message, deduplicated by canonical
    name (e.g. "베르니케" and "베로니카" both resolve to the same entry)."""
    message_lower = message.lower()
    found: list[NamedAreaSynonym] = []
    seen: set[str] = set()
    for keyword, synonym in _NAMED_AREA_SYNONYMS.items():
        if keyword in message_lower and synonym.canonical_ko not in seen:
            found.append(synonym)
            seen.add(synonym.canonical_ko)
    return found


def detect_requested_lobes(message: str) -> list[str]:
    """Real lobe keywords mentioned in the message, in the order they
    appear -- empty if none (no guessing "the user probably means all 4
    lobes" from something like "엽" alone)."""
    found: list[str] = []
    for keyword, lobe in _LOBE_KEYWORDS.items():
        if keyword in message and lobe not in found:
            found.append(lobe)
    return found


def region_ids_for_lobes(lobes: list[str]) -> list[str]:
    if not lobes:
        return []
    macro = get_macro_connectome()
    lobe_set = set(lobes)
    return [r.id for r in macro.regions if lobe_for_anatomical_label(r.anatomical_label) in lobe_set]


@lru_cache
def _disorder_region_ids_by_name() -> dict[str, list[str]]:
    macro = get_macro_connectome()
    return {d.name: d.region_ids for d in macro.known_disorders}


def region_ids_for_used_sources(used_source_ids: list[str]) -> list[str]:
    """The 3D-highlight counterpart to a chat answer's `used_source_ids` --
    same real data the disorder side panel already uses to highlight
    (DisorderAssociation.region_ids, see docs/21), just triggered from a
    chat answer instead of a button click. A "region:<id>" source
    highlights that one region; a "disorder:<name>" source highlights all
    of that disorder's real affected regions. Never guessed -- an id this
    project doesn't recognize (e.g. the model hallucinated a source id) is
    silently dropped, not highlighted."""
    by_region = _region_doc_ids_by_region_id()
    by_disorder = _disorder_region_ids_by_name()
    region_ids: list[str] = []
    seen: set[str] = set()

    def _add(rid: str) -> None:
        if rid not in seen:
            region_ids.append(rid)
            seen.add(rid)

    for source_id in used_source_ids:
        if source_id.startswith("region:"):
            rid = source_id.removeprefix("region:")
            if rid in by_region:
                _add(rid)
        elif source_id.startswith("disorder:"):
            name = source_id.removeprefix("disorder:")
            for rid in by_disorder.get(name, []):
                _add(rid)
        # "gene:*" sources have no region mapping in this dataset -- skipped.

    return region_ids


@lru_cache
def _load_doc_embeddings() -> dict[str, list[float]]:
    """Precomputed corpus embeddings (docs/31), built once offline by
    `backend/scripts/build_human_chat_embeddings.py` and committed as a real
    data artifact -- never recomputed at request time. Returns {} (not an
    error) if the file is missing, so semantic search degrades gracefully
    to keyword-only retrieval rather than breaking the chat endpoint."""
    if not EMBEDDINGS_PATH.exists():
        return {}
    try:
        payload = json.loads(EMBEDDINGS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.exception("Failed to read human chat embeddings file at %s", EMBEDDINGS_PATH)
        return {}
    if payload.get("model") != EMBEDDING_MODEL or payload.get("dimensions") != EMBEDDING_DIMENSIONS:
        logger.warning("Human chat embeddings file model/dimensions mismatch -- ignoring stale file")
        return {}
    return payload.get("doc_embeddings", {})


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def semantic_search_corpus(message: str, client, exclude_ids: set[str]) -> list[ChatCorpusDoc]:
    """Best-effort semantic retrieval (docs/31) -- embeds the query with the
    OpenAI client the caller already holds (no new client construction
    here), ranks precomputed corpus embeddings by cosine similarity, and
    returns real corpus docs above SEMANTIC_SIMILARITY_THRESHOLD (never
    invents a doc). `exclude_ids` skips whatever `search_corpus` already
    found so the two channels don't duplicate the same context lines.

    Deliberately swallows EVERY failure (missing embeddings file, API
    error, malformed response, or anything else unanticipated) and returns
    [] instead -- the whole body runs under one broad guard so this channel
    can never take the chat endpoint down with it; keyword search +
    on-screen context must keep working even if this one is entirely
    broken."""
    if not message.strip():
        return []
    try:
        doc_embeddings = _load_doc_embeddings()
        if not doc_embeddings:
            return []
        response = client.embeddings.create(model=EMBEDDING_MODEL, input=message, dimensions=EMBEDDING_DIMENSIONS)
        query_vector = response.data[0].embedding

        corpus_by_id = {doc.id: doc for doc in _build_corpus()}
        scored: list[tuple[str, float]] = []
        for doc_id, vector in doc_embeddings.items():
            if doc_id in exclude_ids or doc_id not in corpus_by_id:
                continue
            scored.append((doc_id, _cosine_similarity(query_vector, vector)))
        scored.sort(key=lambda pair: pair[1], reverse=True)

        return [corpus_by_id[doc_id] for doc_id, score in scored[:SEMANTIC_TOP_K] if score >= SEMANTIC_SIMILARITY_THRESHOLD]
    except Exception:
        logger.exception("Human chat semantic search failed -- degrading to keyword-only retrieval")
        return []
