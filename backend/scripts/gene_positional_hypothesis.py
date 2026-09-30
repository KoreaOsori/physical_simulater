"""H3-1 검증 (docs/48): '위치 후보 유전자'(염색체상 시드에 가장 가까운 유전자)는 독립적인 기능 연관
데이터베이스에서 무작위 유전자보다 시드와 더 자주 연관되는가?

- 위치 후보: 연구소 유전자 후보 도구(app/lab/gene_hypothesis.py)가 실제로 내놓는 시드별 상위 8개.
- 독립 기준: STRING v12 (Szklarczyk et al.) 인간(9606) 단백질 연관 점수 -- 공개 API.
  연관 채널을 두 가지로 나눠 본다: combined(전체), 그리고 텍스트마이닝을 뺀 실험+데이터베이스+공발현
  (문헌 공출현이 유명 유전자 쪽으로 치우치는 편향을 줄이기 위해).
- 귀무: 같은 646개 신경계 유전자 목록에서 무작위 8개(시드와 후보 제외)를 뽑았을 때의 연관 비율 분포.

실행(인터넷 필요): backend/.venv/Scripts/python.exe -m scripts.gene_positional_hypothesis
"""

from __future__ import annotations

import json
import random
import urllib.parse
import urllib.request

from app.data.human_data import get_genome
from app.lab.gene_hypothesis import _SEED_GENES, build_gene_pathway_candidates

API = "https://string-db.org/api/json"
CALLER = "neuro-connectome-lab-docs48"
N_PERM = 20000
THRESH = 0.4  # STRING '중간 신뢰도'


def _post(method: str, params: dict) -> list:
    data = urllib.parse.urlencode({**params, "caller_identity": CALLER}).encode()
    with urllib.request.urlopen(urllib.request.Request(f"{API}/{method}", data=data), timeout=120) as r:
        return json.loads(r.read().decode())


def main() -> None:
    genome = get_genome()
    universe = sorted({g.symbol for g in genome.genes})
    seeds = [s.symbol for s in _SEED_GENES]
    reports = {r.seed_symbol: [c.symbol for c in r.candidates] for r in build_gene_pathway_candidates()}

    # 기호 -> STRING 선호 이름(동의어 정리)
    mapped = _post("get_string_ids", {"identifiers": "\r".join(seeds + universe), "species": 9606, "limit": 1, "echo_query": 1})
    to_pref = {m["queryItem"]: m["preferredName"] for m in mapped}
    pref_seeds = [to_pref.get(s) for s in seeds]

    scores: dict[tuple[str, str], dict] = {}
    for seed, ps in zip(seeds, pref_seeds):
        if not ps:
            continue
        partners = _post("interaction_partners", {"identifiers": ps, "species": 9606, "limit": 5000, "required_score": 150})
        for p in partners:
            other = p["preferredName_B"] if p["preferredName_A"] == ps else p["preferredName_A"]
            non_text = 1 - (1 - p.get("escore", 0)) * (1 - p.get("dscore", 0)) * (1 - p.get("ascore", 0))
            scores[(seed, other)] = {"combined": p["score"], "non_textmining": non_text, "channels": {k: p.get(k, 0) for k in ("escore", "dscore", "ascore", "tscore")}}

    def score(seed: str, gene: str, key: str) -> float:
        return scores.get((seed, to_pref.get(gene, gene)), {}).get(key, 0.0)

    rng = random.Random(20260929)
    results = []
    for seed in seeds:
        cands = reports.get(seed, [])
        pool = [g for g in universe if g not in cands and g != seed and g in to_pref]
        row = {"seed": seed, "candidates": []}
        for g in cands:
            row["candidates"].append({"gene": g, "combined": score(seed, g, "combined"), "non_textmining": score(seed, g, "non_textmining"), "channels": scores.get((seed, to_pref.get(g, g)), {}).get("channels")})
        for key in ("combined", "non_textmining"):
            obs = sum(score(seed, g, key) >= THRESH for g in cands) / max(1, len(cands))
            null = [sum(score(seed, g, key) >= THRESH for g in rng.sample(pool, len(cands))) / len(cands) for _ in range(N_PERM)]
            base_rate = sum(score(seed, g, key) >= THRESH for g in pool) / len(pool)
            row[key] = {"observed_frac": obs, "universe_rate": base_rate, "p_ge": (sum(n >= obs for n in null) + 1) / (N_PERM + 1)}
        results.append(row)

    # 전체 시드 합산(위치 후보 48개 vs 무작위)
    pooled = {}
    for key in ("combined", "non_textmining"):
        obs = sum(sum(score(r["seed"], c["gene"], key) >= THRESH for c in r["candidates"]) for r in results)
        n = sum(len(r["candidates"]) for r in results)
        null = []
        for _ in range(N_PERM):
            k = 0
            for r in results:
                pool = [g for g in universe if g not in reports[r["seed"]] and g != r["seed"] and g in to_pref]
                k += sum(score(r["seed"], g, key) >= THRESH for g in rng.sample(pool, len(r["candidates"])))
            null.append(k)
        pooled[key] = {"observed": obs, "n": n, "null_mean": sum(null) / N_PERM, "p_ge": (sum(x >= obs for x in null) + 1) / (N_PERM + 1)}

    print(json.dumps({"threshold": THRESH, "universe_size": len(universe), "mapped": len(to_pref), "per_seed": results, "pooled": pooled, "bdnf_slc1a2": scores.get(("BDNF", to_pref.get("SLC1A2", "SLC1A2")))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
