"""Lausanne 462 반복 촬영 병전 지도 추정 스크립트 테스트(docs/61, H17-15)."""

import random
from pathlib import Path

import numpy as np
import pytest

from scripts import lausanne_retest_premorbid as lr

N = lr.N
HCP = Path(__file__).resolve().parents[2] / "zenodo-14017270" / "HCP" / "data_nobrainstem"


def test_impute_fills_only_lesion_pairs_with_expected_count() -> None:
    m = len(lr.IU[0])
    rng = np.random.default_rng(0)
    obs = rng.random(m) < 0.05
    touch = np.zeros(m, dtype=bool)
    touch[:500] = True
    freq = np.zeros(m)
    freq[:10] = 1.0
    freq[10:20] = 0.5
    out = lr.impute(obs, touch, freq, np.arange(m, dtype=float))
    assert (out[~touch] == obs[~touch]).all()
    assert out[:500].sum() == 15
    assert out[:10].all()


def test_reorganize_key_reconnects_lost_stubs_within_reach() -> None:
    rng = np.random.default_rng(1)
    adj = lr.to_adj(rng.random(len(lr.IU[0])) < 0.05)
    alive = np.ones(N, dtype=bool)
    alive[:10] = False
    adj[:10, :] = False
    adj[:, :10] = False
    dist = np.ones((N, N))
    lost = {20: 2, 30: 1}
    out = lr.reorganize_key(adj, alive, lost, dist, 1.0, lambda b, c: b[c], random.Random(0))
    added = np.argwhere(np.triu(out & ~adj, 1))
    assert len(added) == 3
    assert not out[:10].any()


@pytest.mark.skipif(not HCP.exists(), reason="Zenodo 14017270 HCP 데이터가 없다(git 제외 폴더)")
def test_lesions_defined_by_desikan_names() -> None:
    c = lr.load_cohort(str(HCP))
    assert c["vecs"].shape == (44, len(lr.IU[0]))
    assert c["k"] == int(round(lr.DENSITY * len(lr.IU[0])))
    sizes = {x["name"]: len(x["nodes"]) for x in c["lesions"]}
    assert sizes["베르니케 실어증(14)"] == 14
    assert all(s >= 10 for s in sizes.values())
    for x in c["lesions"]:
        assert all(0 <= i < N for i in x["nodes"])
