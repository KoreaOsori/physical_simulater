"""병전 지도 추정 스크립트 테스트(docs/59, H17-13).

실제 코호트(MICA-MICs)를 받으면 바로 쓸 로더와 채워 넣기 함수가 의도대로 동작하는지 확인한다."""

import numpy as np
import pytest

from scripts import premorbid_map_estimation as pm
from scripts.synthetic_individual_cohort import IU

N = pm.N


def _random_weights(seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    m = rng.random((N, N))
    m = np.triu(m, 1)
    return m


def test_loader_symmetrizes_upper_triangle_and_keeps_top_edges(tmp_path) -> None:
    for i in range(3):
        d = tmp_path / f"sub-HC00{i}" / "ses-01"
        d.mkdir(parents=True)
        np.savetxt(d / f"sub-HC00{i}_atlas-schaefer-400_full-connectome.txt", _random_weights(i))
        # 길이 행렬은 무시되어야 한다
        np.savetxt(d / f"sub-HC00{i}_atlas-schaefer-400_full-edgeLengths.txt", np.ones((N, N)))
    names, vecs = pm.load_real_cohort(str(tmp_path), n_edges=500)
    assert names == ["sub-HC000", "sub-HC001", "sub-HC002"]
    for i, v in enumerate(vecs):
        assert v.sum() == 500
        w = _random_weights(i)[IU]
        assert w[v].min() >= w[~v].max()  # 상위 500개


def test_loader_requires_offset_for_larger_matrix(tmp_path, monkeypatch) -> None:
    d = tmp_path / "sub-HC001"
    d.mkdir()
    big = np.zeros((N + 14, N + 14))
    big[14:, 14:] = _random_weights(0) + _random_weights(0).T
    np.save(d / "sub-HC001_schaefer400_sc.npy", big)
    monkeypatch.delenv("MICA_OFFSET", raising=False)
    with pytest.raises(SystemExit):
        pm.load_real_cohort(str(tmp_path), n_edges=100)
    monkeypatch.setenv("MICA_OFFSET", "14")
    _, vecs = pm.load_real_cohort(str(tmp_path), n_edges=100)
    assert vecs[0].sum() == 100


def test_impute_only_touches_lesion_pairs_with_expected_count() -> None:
    rng = np.random.default_rng(0)
    n_pairs = len(IU[0])
    obs = rng.random(n_pairs) < 0.05
    les = np.zeros(N, dtype=bool)
    les[:10] = True
    touch = les[IU[0]] | les[IU[1]]
    freq = rng.random(n_pairs) * 0.1
    out = pm.impute(obs, touch, freq, np.zeros(n_pairs))
    assert np.array_equal(out[~touch], obs[~touch])  # 병변 밖은 관측 그대로
    assert out[touch].sum() == int(round(freq[touch].sum()))
    chosen = freq[touch][out[touch]]
    assert chosen.min() >= freq[touch][~out[touch]].max()  # 빈도 높은 쌍부터


def test_loader_reads_micapipe_416_layout(tmp_path) -> None:
    # micapipe: 0~13 피질하, 14·215 내측벽(빈 행), 15~214 좌반구, 216~415 우반구. 상삼각, 쉼표 구분.
    d = tmp_path / "sub-HC001" / "ses-01" / "dwi"
    d.mkdir(parents=True)
    w = _random_weights(0)
    big = np.zeros((416, 416))
    big[np.ix_(pm.MICAPIPE_CORTEX, pm.MICAPIPE_CORTEX)] = w
    big[:14, :14] = np.triu(np.full((14, 14), 99.0), 1)  # 피질하 강한 연결은 무시되어야 한다
    np.savetxt(d / "sub-HC001_ses-01_space-dwinative_atlas-schaefer400_desc-sc.txt", big, delimiter=",")
    np.savetxt(d / "sub-HC001_ses-01_space-dwinative_atlas-schaefer400_desc-edgeLength.txt", big, delimiter=",")
    _, vecs = pm.load_real_cohort(str(tmp_path), n_edges=300)
    wu = w[IU]
    assert vecs[0].sum() == 300
    assert wu[vecs[0]].min() >= wu[~vecs[0]].max()
