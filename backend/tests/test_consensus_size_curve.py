"""합의 지도 참조 인원 곡선 스크립트 테스트(docs/62, H17-16)."""

from scripts import consensus_size_curve as cs


def _rows() -> list[dict]:
    rows = []
    for u in range(3):
        for li in range(2):
            base = {"unit": [u, 0], "lesion": li}
            rows.append({**base, "guide": "distributed", "casc_m1.2": 0.6, "casc_m1.0": 0.5})
            rows.append({**base, "guide": "n49_r0", "casc_m1.2": 0.8, "casc_m1.0": 0.7, "spearman": 0.8})
            for r, v in enumerate((0.6, 0.7, 0.8)):
                rows.append({**base, "guide": f"n1_r{r}", "casc_m1.2": v, "casc_m1.0": 0.5, "spearman": 0.6})
    return rows


def test_summary_pools_draws_and_scales_between_distributed_and_full() -> None:
    s = cs.summarize("mica", _rows())
    assert set(s) == {"distributed", "n49", "n1"}
    n1 = s["n1"]["casc_m1.2"]
    assert abs(n1["mean"] - 0.7) < 1e-12
    assert abs(n1["minus_full"] + 0.1) < 1e-12
    assert abs(n1["frac_of_full_over_distributed"] - 0.5) < 1e-12
    assert abs(s["n49"]["casc_m1.2"]["frac_of_full_over_distributed"] - 1.0) < 1e-9
    assert abs(s["distributed"]["casc_m1.0"]["frac_of_full_over_distributed"]) < 1e-9
    assert s["n1"]["n_rows"] == 18
    assert abs(s["n1"]["spearman"] - 0.6) < 1e-12
