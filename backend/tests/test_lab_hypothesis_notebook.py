"""가설 노트 테스트 (docs/39-40). H1은 실시간 계산이라 실제 값으로 검증하고,
H2-H6는 정적 기록이라 필드가 정직하게 채워져 있는지(빈 값·거짓 verdict
없는지)를 확인한다."""

from fastapi.testclient import TestClient

from app.lab.hypothesis_notebook import build_hypothesis_notebook
from app.main import app

client = TestClient(app)

_STATIC_RECORD_IDS = [
    "h2-dva-topological-hub",
    "h3-slc1a2-bdnf-candidate",
    "h4-frontal-sup-medial-gap",
    "h5-small-world-cross-species",
    "h6-connector-hub-cross-species",
]


_CLOSED_LOOP_RECORD_IDS = {
    "h7-worm-chemotaxis-blind-zone": "supported",
    "h8-worm-ase-asymmetry-in-connectome": "not_supported",
    "h9-worm-klinokinesis-closed-loop": "supported",
    "h10-worm-correct-ase-polarity-breaks-loop": "supported",
    "h11-fly-avoidance-sphere": "supported",
    "h12-fly-random-avoidance-leaky-zone": "not_supported",
}


_FIX_RECORD_IDS = {
    "h13-worm-receptor-signs-rescue-polarity": "supported",
    "h14-worm-default-start-in-band": "supported",
    "h15-fly-directed-avoidance-seals-zone": "supported",
}


_FOLLOWUP_RECORD_IDS = {
    "h1-1-full-graph-reanalysis": "inconclusive",
    "h1-2-per-disorder-hubness": "inconclusive",
    "h1-3-receptor-plus-centrality-model": "inconclusive",
    "h1-4-complex-vs-focal-disorders": "supported",
    "h1-5-alzheimer-functional-hubs": "not_supported",
    "h2-1-all-neuron-silencing-vs-centrality": "supported",
    "h2-2-closed-loop-silencing": "supported",
    "h2-3-avb-input-balance-counterfactual": "inconclusive",
    "h3-1-positional-candidate-specificity": "supported",
}


_REORG_RECORD_IDS = {
    "h16-equal-hub-distribution-after-lesion": "inconclusive",
    "h16-1-lesion-hubness-not-size": "supported",
    "h16-2-concentrated-recovers-efficiency": "not_supported",
    "h16-3-distributed-evens-load": "supported",
    "h16-4-distributed-resists-second-hit": "supported",
    "h16-5-capacity-aware-distribution": "supported",
}


# docs/51: 외부 검토 의견에 따른 강건성 후속(부모 가설 바로 아래)
_ROBUSTNESS_RECORD_IDS = {
    "h16-1-1-hubness-effect-robustness": ("h16-1-lesion-hubness-not-size", "lesion_hubness_robustness.py", "supported"),
    "h16-2-1-short-vs-long-term-optima": ("h16-2-concentrated-recovers-efficiency", "short_long_term_reorganization.py", "supported"),
    "h16-5-1-capacity-definition-sensitivity": ("h16-5-capacity-aware-distribution", "capacity_definition_sensitivity.py", "not_supported"),
    "h16-5-2-headroom-not-algorithm-artifact": ("h16-5-1-capacity-definition-sensitivity", "headroom_robustness_suite.py", "supported"),
    # docs/52
    "h16-1-2-which-hubness-predicts-impact": ("h16-1-1-hubness-effect-robustness", "hubness_types.py", "supported"),
    "h16-5-3-null-network-distribution": ("h16-5-2-headroom-not-algorithm-artifact", "null_network_distribution.py", "supported"),
}


def test_hypothesis_notebook_has_all_records() -> None:
    records = build_hypothesis_notebook()
    ids = {r.id for r in records}
    assert len(records) == 51
    assert ids == {
        "h1-disease-hub-correlation",
        *_STATIC_RECORD_IDS,
        *_CLOSED_LOOP_RECORD_IDS,
        *_FIX_RECORD_IDS,
        *_FOLLOWUP_RECORD_IDS,
        *_REORG_RECORD_IDS,
        *_ROBUSTNESS_RECORD_IDS,
        *_H17_RECORD_IDS,
    }


def test_reorganization_records_keep_real_verdicts_in_order() -> None:
    # docs/50: 사용자 가설 H16(혼재 -> 미확정)과 후속 H16-1~H16-5는 마지막에 순서대로, 문헌 정정(Griffis=Cell Reports) 포함
    records = build_hypothesis_notebook()
    assert [r.id for r in records if r.id not in _ROBUSTNESS_RECORD_IDS and r.id not in _H17_RECORD_IDS][-6:] == list(_REORG_RECORD_IDS)
    by_id = {r.id: r for r in records}
    for hid, verdict in _REORG_RECORD_IDS.items():
        r = by_id[hid]
        assert r.verdict == verdict
        assert r.executed_at == "2026-09-29"
        assert r.is_live_computed is False
        assert "reorganization_hypotheses.py" in r.method
        assert r.raw_data_note
        assert all(e.url.startswith("https://") for e in r.evidence)
    assert "Cell Reports" in by_id["h16-equal-hub-distribution-after-lesion"].raw_data_note
    assert "0.895" in by_id["h16-5-capacity-aware-distribution"].raw_data_note


# docs/52: H17(정상 부하 지도 기반 재조직)과 후속은 노트 맨 끝에 순서대로
_H17_RECORD_IDS = {
    "h17-normative-load-map-reorganization": "supported",
    "h17-1-restoring-the-load-map-and-circularity": "supported",
    "h17-2-mixed-failure-parameter-recovery": "supported",
    "h17-3-best-strategy-by-failure-mixture": "supported",
    "h17-4-closed-loop-rehab": "inconclusive",
    # docs/53
    "h17-5-representative-connectome-sensitivity": "inconclusive",
    "h17-6-synthetic-individual-envelope": "inconclusive",
    # docs/55
    "h17-7-tau-constraint-pareto": "supported",
    # docs/56
    "h17-8-staged-adaptive-under-threshold-uncertainty": "supported",
    "h17-9-pair-flow-decomposition": "inconclusive",
    "h17-10-weighted-strengthening-model": "not_supported",
    # docs/57
    "h17-11-why-weighted-model-flips": "inconclusive",
    # docs/58
    "h17-12-time-matched-strategy": "inconclusive",
    # docs/59
    "h17-13-premorbid-map-from-own-scan": "inconclusive",
    # docs/60
    "h17-14-real-test-retest-scan-noise": "not_supported",
}


def test_h17_records_close_the_notebook_with_real_verdicts() -> None:
    records = build_hypothesis_notebook()
    assert [r.id for r in records[-len(_H17_RECORD_IDS):]] == list(_H17_RECORD_IDS)
    by_id = {r.id: r for r in records}
    for hid, verdict in _H17_RECORD_IDS.items():
        r = by_id[hid]
        assert r.verdict == verdict
        assert r.executed_at in ("2026-10-02", "2026-10-03", "2026-10-06")
        assert r.raw_data_note
    # 검토 의견 8번: '특정 정상 뇌'가 아니라 '정상 집단 대표 커넥톰'
    assert "정상 집단 대표" in h17_title_and_statement(by_id)
    # 9번: 합성 코호트는 실제 σ 크기를 주장하지 않는다
    assert "실제 σ의 크기를 말하지 않는다" in by_id["h17-6-synthetic-individual-envelope"].result_summary
    # 검토 의견 9·17번: 이름과 조건이 정직하게 들어가 있는지
    h17 = by_id["h17-normative-load-map-reorganization"]
    assert "정상 부하 지도 기반" in h17.statement and "연쇄형" in h17.statement
    assert "실패 문턱이 정상 부하에 비례" in by_id["h17-1-restoring-the-load-map-and-circularity"].result_summary
    # 검토 의견 13번: n=2는 '강한 탐색적 근거'로 정정
    assert "강한 탐색적 근거" in by_id["h16-5-2-headroom-not-algorithm-artifact"].result_summary


def test_robustness_followups_sit_right_after_their_parent() -> None:
    records = build_hypothesis_notebook()
    order = [r.id for r in records]
    by_id = {r.id: r for r in records}
    for hid, (parent, script, verdict) in _ROBUSTNESS_RECORD_IDS.items():
        assert order.index(hid) == order.index(parent) + 1
        r = by_id[hid]
        assert r.verdict == verdict
        assert r.executed_at in ("2026-09-30", "2026-10-02")
        assert r.is_live_computed is False
        assert script in r.method
        assert r.raw_data_note
    # docs/51 정정: H16-1의 0.69는 Pearson이 아니라 Spearman
    assert "Spearman" in by_id["h16-1-1-hubness-effect-robustness"].result_summary


def test_followups_sit_right_after_their_parent_and_keep_real_verdicts() -> None:
    # docs/48: H1-x/H2-x/H3-x는 부모 가설 바로 아래, 판정(기각·미확정 포함)은 실제 결과 그대로
    records = build_hypothesis_notebook()
    order = [r.id for r in records]
    assert order[:6] == ["h1-disease-hub-correlation", *[k for k in _FOLLOWUP_RECORD_IDS if k.startswith("h1-")]]
    assert order[order.index("h2-dva-topological-hub") + 1].startswith("h2-1")
    assert order[order.index("h3-slc1a2-bdnf-candidate") + 1].startswith("h3-1")
    by_id = {r.id: r for r in records}
    for hid, verdict in _FOLLOWUP_RECORD_IDS.items():
        r = by_id[hid]
        assert r.verdict == verdict
        assert r.executed_at == "2026-09-29"
        assert r.raw_data_note
        assert r.title.startswith(hid.split("-")[0].upper() + "-" + hid.split("-")[1] + " ·")
        assert all(e.url.startswith("https://") for e in r.evidence)


def test_fix_records_keep_their_verdicts_and_raw_data() -> None:
    # docs/47: 모델 수정 후 재검증 기록
    records = {r.id: r for r in build_hypothesis_notebook()}
    for hid, verdict in _FIX_RECORD_IDS.items():
        r = records[hid]
        assert r.verdict == verdict
        assert r.executed_at == "2026-09-29"
        assert r.raw_data_note
        assert all(e.url.startswith("https://") for e in r.evidence)


def test_closed_loop_records_keep_their_real_verdicts_and_raw_data() -> None:
    # docs/46: 폐루프로 실제 실행한 결과 -- 기각된 가설(H8, H12)도 기각으로 남아 있어야 한다.
    records = {r.id: r for r in build_hypothesis_notebook()}
    for hid, verdict in _CLOSED_LOOP_RECORD_IDS.items():
        r = records[hid]
        assert r.verdict == verdict
        assert r.is_live_computed is False
        assert r.executed_at == "2026-09-28"
        assert r.raw_data_note
        assert "closed_loop_hypotheses.py" in r.method
        assert all(e.url.startswith("https://") for e in r.evidence)


def test_h1_is_live_computed_with_real_correlation() -> None:
    records = build_hypothesis_notebook()
    h1 = next(r for r in records if r.id == "h1-disease-hub-correlation")
    assert h1.is_live_computed is True
    assert h1.executed_at is None

    # docs/49: 원본 전체 커넥톰(네트워크 간 간선 복구)으로 계산 -- r≈0.186 → 규칙상 '미확정'(0.1≤|r|<0.3).
    # 복구 전(끊어진 그래프)엔 r=0.0501로 '기각'이었다.
    assert h1.verdict == "inconclusive"
    assert "0.1859" in h1.raw_data_note
    assert "피어슨" in h1.raw_data_note


def test_h1_recomputes_identically_on_repeated_calls() -> None:
    # deterministic real graph computation -- same input data every time,
    # should yield byte-identical results, not something that drifts.
    first = build_hypothesis_notebook()
    second = build_hypothesis_notebook()
    h1_first = next(r for r in first if r.id == "h1-disease-hub-correlation")
    h1_second = next(r for r in second if r.id == "h1-disease-hub-correlation")
    assert h1_first.result_summary == h1_second.result_summary


def test_h2_through_h6_are_static_records_with_real_citations() -> None:
    records = build_hypothesis_notebook()
    for hid in _STATIC_RECORD_IDS:
        record = next(r for r in records if r.id == hid)
        assert record.is_live_computed is False
        assert record.executed_at == "2026-09-24"
        assert len(record.evidence) > 0
        for e in record.evidence:
            assert e.url.startswith("https://")
            assert e.title


def test_h6_reports_mixed_cross_species_verdict_honestly() -> None:
    # Real finding this session: DVA's participation coefficient supports
    # the worm-side hypothesis, but the human macro graph's near-zero
    # average participation coefficient does NOT support generalizing the
    # pattern -- this must stay "inconclusive", not get rounded up to
    # "supported" just because one species worked out.
    records = build_hypothesis_notebook()
    h6 = next(r for r in records if r.id == "h6-connector-hub-cross-species")
    assert h6.verdict == "inconclusive"
    assert "0.7943" in h6.raw_data_note  # real DVA participation coefficient
    assert "0.0039" in h6.raw_data_note  # real human average, near zero


def test_hypothesis_notebook_endpoint_returns_200() -> None:
    response = client.get("/api/lab/hypotheses")
    assert response.status_code == 200
    assert len(response.json()) == 51


def h17_title_and_statement(by_id) -> str:
    r = by_id["h17-normative-load-map-reorganization"]
    return r.title + r.statement
