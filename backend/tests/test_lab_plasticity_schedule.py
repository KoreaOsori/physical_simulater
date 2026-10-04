"""시기 맞춤 재조직(가중치 모델) 테스트(docs/58, H17-12).

서버 구현(app/lab/plasticity_schedule.py)이 검증 스크립트(scripts/time_varying_plasticity.py)와 같은 계산인지:
가중 betweenness가 networkx와 같고, 같은 병변·일정·정책이면 재조직 결과 가중치 행렬이 완전히 같다."""

import random

import networkx as nx
import numpy as np
from fastapi.testclient import TestClient

from app.lab import plasticity_schedule as ps
from app.lab import reorganization_lab as rl
from app.main import app

client = TestClient(app)


def test_weighted_betweenness_matches_networkx() -> None:
    wb = ps._wbase()
    G = nx.Graph()
    for i, j in zip(*np.nonzero(np.triu(wb.W0, 1))):
        G.add_edge(int(i), int(j), length=1.0 / wb.W0[i, j])
    ref = nx.betweenness_centrality(G, normalized=False, weight="length")
    assert max(abs(wb.L0[i] - ref[i]) for i in range(rl.N)) < 1e-6


def test_server_schedule_equals_verification_script() -> None:
    import scripts.time_varying_plasticity as tv

    b = rl._base()
    li = 8
    lesion_id = [x["id"] for x in b.lesions if x["category"] == "focal"][li]
    wb = ps._wbase()
    Wl, alive, lost_k, lost_s = ps.lesion_setup(lesion_id)
    for schedule in ("seq", "ramp"):
        mine = ps.run_schedule(Wl, alive, lost_k, lost_s, schedule, ps.POLICIES["matched"][1], wb.cap, wb.eps, li * 1000)
        ref = tv.run(Wl, alive, lost_k, lost_s, b.dist, b.lmax, schedule, tv.POLICIES["맞춤(강화=분산, 발아=τ0)"], wb.cap, wb.eps, li * 1000, lambda W: None)
        assert np.array_equal(mine, ref), schedule


def test_api_returns_policies_and_schedule_profile() -> None:
    r = client.post("/api/lab/reorganization/plasticity-schedule", json={"lesion_id": "d1", "schedule": "seq", "policies": ["dist", "matched"]})
    assert r.status_code == 200
    body = r.json()
    assert [x["policy"] for x in body["results"]] == ["none", "dist", "matched"]
    # 순차 일정: 앞 절반은 강화(발아 0), 뒤 절반은 발아(1)
    prof = body["sprout_fraction_by_decile"]
    assert len(prof) == 10 and prof[0] == 0.0 and prof[-1] == 1.0
    for x in body["results"]:
        for ph in ("mid", "end"):
            assert 0 <= x[ph]["casc_m12"] <= 1 and 0 <= x[ph]["casc_m10"] <= 1
    # 맞춤 정책은 강화 단계에서 균등 분산과 같은 규칙이라 중간 결과가 같다
    res = {x["policy"]: x for x in body["results"]}
    assert res["matched"]["mid"] == res["dist"]["mid"]
    assert "검색 요약" in body["honesty_note"]


def test_unknown_lesion_is_404() -> None:
    r = client.post("/api/lab/reorganization/plasticity-schedule", json={"lesion_id": "nope", "policies": ["dist"]})
    assert r.status_code == 404
