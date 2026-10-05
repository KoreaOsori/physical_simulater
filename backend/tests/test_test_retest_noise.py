"""반복 촬영 잡음 측정 스크립트 테스트(docs/60, H17-14)."""

import numpy as np

from scripts import test_retest_noise as tr


def test_pair_stats_identical_and_disjoint() -> None:
    n = 20
    iu = np.triu_indices(n, 1)
    rng = np.random.default_rng(0)
    a = rng.random(len(iu[0])) < 0.3
    la = tr.betweenness(a, n)
    same = tr.pair_stats(a, a, la, la)
    assert same["swap"] == 0.0
    assert same["load_spearman"] > 0.999
    assert same["hub_overlap"] == 1.0
    b = ~a
    assert tr.pair_stats(a, b, la, tr.betweenness(b, n))["swap"] == 1.0


def test_betweenness_matches_path_graph() -> None:
    # 경로 0-1-2-3: 가운데 두 노드만 매개, 비정규화 값 2
    n = 4
    iu = np.triu_indices(n, 1)
    vec = np.zeros(len(iu[0]), dtype=bool)
    for x, y in [(0, 1), (1, 2), (2, 3)]:
        vec[np.flatnonzero((iu[0] == x) & (iu[1] == y))] = True
    assert tr.betweenness(vec, n).tolist() == [0.0, 2.0, 2.0, 0.0]


def test_invert_interpolates_both_directions() -> None:
    grid = {"0.0": {"swap": {"mean": 0.0}, "rho": {"mean": 1.0}},
            "0.1": {"swap": {"mean": 0.2}, "rho": {"mean": 0.6}}}
    assert abs(tr.invert(grid, "swap", 0.1) - 0.05) < 1e-12
    assert abs(tr.invert(grid, "rho", 0.8) - 0.05) < 1e-12
    assert tr.invert(grid, "rho", 0.5) is None
