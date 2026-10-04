"""손상-재조직 실험실 · 폐루프 재활 테스트(docs/52).

서버 구현(app/lab/reorganization_lab.py)이 검증 스크립트와 같은 계산을 하는지가 핵심이다:
  - numpy 매개 중심성·전역 효율 = networkx 값
  - 재조직 규칙 = scripts/reorganization_hypotheses.reorganize()와 같은 간선 집합(같은 시드)
그리고 API가 정직한 범위 안의 값을 돌려주는지 본다(계산 비용 때문에 시기·반복은 작게)."""

import random

import networkx as nx
import numpy as np
from fastapi.testclient import TestClient

from app.lab import reorganization_lab as rl
from app.main import app

client = TestClient(app)


def test_numpy_betweenness_and_efficiency_match_networkx() -> None:
    b = rl._base()
    alive = b.alive0.copy()
    alive[list(range(0, 400, 6))] = False
    adj = rl.strip(b.adj0, alive)
    g = nx.from_numpy_array(adj.astype(int))
    g.remove_nodes_from([i for i in range(400) if not alive[i]])
    ref = nx.betweenness_centrality(g, normalized=False)
    ours = rl.betweenness(adj, alive)
    assert max(abs(ours[i] - ref[i]) for i in g.nodes) < 1e-6
    assert np.all(ours[~alive] == 0)
    eff = nx.global_efficiency(g) * len(g) * (len(g) - 1) / (400 * 399)
    assert abs(rl.abs_efficiency(adj, alive) - eff) < 1e-9


def test_reorganize_matches_the_verification_script_edge_for_edge() -> None:
    from scripts.reorganization_hypotheses import load, reorganize

    g, dist, _, lesions = load()
    b = rl._base()
    cap = {i: float(b.cap[i]) for i in range(400)}
    lmax = float(np.percentile([dist[x, y] for x, y in g.edges], 75))
    assert abs(lmax - b.lmax) < 1e-9
    li = 13  # 국소 증후군 13번(scripts와 같은 번호)
    lesion_id = [x["id"] for x in b.lesions if x["category"] == "focal"][li]
    assert set(b.lesion(lesion_id)["nodes"]) == set(lesions[li]["nodes"])
    adj_l, alive, lost = rl._lesioned(b, lesion_id)
    gl = g.copy()
    gl.remove_nodes_from(lesions[li]["nodes"])
    for ours, theirs in [("normative", "headroom"), ("distributed", "distributed"), ("random", "random"), ("concentrated", "concentrated")]:
        ref = reorganize(gl, lost, dist, lmax, theirs, random.Random(li * 1000), cap)
        got = rl.reorganize(adj_l, alive, lost, ours, random.Random(rl._seed(lesion_id)))
        a, c = np.nonzero(np.triu(got, 1))
        assert {tuple(sorted(e)) for e in ref.edges} == set(zip(a.tolist(), c.tolist())), ours


def test_meta_lists_real_lesions_and_strategies() -> None:
    r = client.get("/api/lab/reorganization/meta")
    assert r.status_code == 200
    body = r.json()
    assert len(body["lesions"]) == 32
    assert sum(x["category"] == "focal" for x in body["lesions"]) == 25
    assert body["strategies"] == ["none", "local", "concentrated", "distributed", "normative", "random", "tau"]
    assert body["strategy_labels"]["normative"] == "정상 부하 지도 기반"
    assert "환자 데이터가 아니며" in body["honesty_note"]


def test_lab_run_returns_bounded_metrics_and_normative_keeps_the_load_map() -> None:
    r = client.post("/api/lab/reorganization/run", json={"lesion_id": "d0", "strategies": ["none", "distributed", "normative"], "epochs": 2, "reps": 1, "w1": 1, "w2": 0, "w3": 0, "w4": 0})
    assert r.status_code == 200
    body = r.json()
    res = {x["strategy"]: x for x in body["results"]}
    assert body["mixture"] == [1.0, 0.0, 0.0, 0.0]
    assert res["none"]["edges_added"] == 0
    assert res["normative"]["edges_added"] == res["distributed"]["edges_added"] == body["edges_lost"]
    for x in res.values():
        assert 0 <= x["cascade_survival"] <= 1 and 0 <= x["overload_frac"] <= 1
        assert len(x["wear_mean"]) == 3
        assert all(a >= b - 1e-12 for a, b in zip(x["wear_mean"], x["wear_mean"][1:]))  # 영역은 늘지 않는다
    # docs/50-52 핵심 결과의 회귀 고정: 정상 부하 지도 기반은 균등 분산보다 정상 부하 지도를 잘 보존하고 연쇄에 강하다
    assert res["normative"]["loadmap_rho"] > res["distributed"]["loadmap_rho"]
    assert res["normative"]["overload_frac"] < res["distributed"]["overload_frac"]
    assert res["normative"]["cascade_survival"] > res["distributed"]["cascade_survival"]


def test_unknown_lesion_is_404() -> None:
    r = client.post("/api/lab/reorganization/run", json={"lesion_id": "nope", "strategies": ["none"], "epochs": 1, "reps": 1})
    assert r.status_code == 404


def test_closed_loop_modulation_only_helps_relative_overload_failure() -> None:
    # 활동 조절은 부하를 옮길 뿐(총량 보존)이라: W1(자기 정상 부하 대비, 비선형)에서는 도움이 되고,
    # W3(부하 무관)에서는 개입이 있어도 결과가 개입 없음과 똑같아야 한다(공통 난수).
    common = {"lesion_id": "d0", "mode": "modulate", "budget": 20, "epochs": 6, "reps": 2, "base_strategy": "distributed"}
    w1 = client.post("/api/lab/reorganization/closed-loop", json={**common, "w1": 1, "w2": 0, "w3": 0, "w4": 0}).json()
    t = {x["controller"]: x for x in w1["traces"]}
    assert sum(t["closed"]["interventions"]) > 0 and sum(t["none"]["interventions"]) == 0
    assert t["closed"]["alive"][-1] >= t["none"]["alive"][-1]
    w3 = client.post("/api/lab/reorganization/closed-loop", json={**common, "w1": 0, "w2": 0, "w3": 1, "w4": 0}).json()
    t3 = {x["controller"]: x for x in w3["traces"]}
    assert t3["closed"]["alive"] == t3["none"]["alive"]
    assert len(w3["regions"]) == 400


def test_closed_loop_connect_respects_the_same_total_budget() -> None:
    r = client.post("/api/lab/reorganization/closed-loop", json={"lesion_id": "d0", "mode": "connect", "budget": 100, "epochs": 8, "reps": 1, "w1": 0, "w2": 0, "w3": 1, "w4": 0})
    assert r.status_code == 200
    t = {x["controller"]: x for x in r.json()["traces"]}
    planned = r.json()["edges_lost"]
    assert sum(t["open"]["interventions"]) <= planned
    assert sum(t["closed"]["interventions"]) <= planned
    assert all(v <= 100 for v in t["closed"]["interventions"])


def test_tau_strategy_endpoints_equal_normative_and_concentrated() -> None:
    # docs/55: τ=0 == 정상 부하 지도 기반, τ가 아주 크면 == 허브 집중(간선까지 같음)
    b = rl._base()
    lesion_id = [x["id"] for x in b.lesions if x["category"] == "focal"][7]
    adj_l, alive, lost = rl._lesioned(b, lesion_id)
    seed = rl._seed(lesion_id)
    t0 = rl.reorganize(adj_l, alive, lost, "tau", random.Random(seed), tau=0.0)
    nm = rl.reorganize(adj_l, alive, lost, "normative", random.Random(seed))
    assert (t0 == nm).all()
    tinf = rl.reorganize(adj_l, alive, lost, "tau", random.Random(seed), tau=1e9)
    cc = rl.reorganize(adj_l, alive, lost, "concentrated", random.Random(seed))
    assert (tinf == cc).all()
