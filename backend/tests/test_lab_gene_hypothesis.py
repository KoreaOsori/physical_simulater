"""연구소(Lab) 유전자 경로 후보 가설 탐색기 테스트 (docs/37)."""

from fastapi.testclient import TestClient

from app.lab.gene_hypothesis import build_gene_pathway_candidates
from app.main import app

client = TestClient(app)


def test_gene_pathway_candidates_cover_all_six_seed_genes() -> None:
    reports = build_gene_pathway_candidates()
    seed_symbols = {r.seed_symbol for r in reports}
    assert seed_symbols == {"BDNF", "CREB1", "NTRK2", "GRIN2B", "CAMK2A", "ARC"}


def test_gene_pathway_candidates_are_real_genes_on_the_same_chromosome() -> None:
    reports = build_gene_pathway_candidates()
    bdnf_report = next(r for r in reports if r.seed_symbol == "BDNF")
    assert bdnf_report.seed_chromosome == "11"
    assert len(bdnf_report.candidates) > 0
    for c in bdnf_report.candidates:
        assert c.chromosome == "11"
        # never the seed genes themselves or other pathway seeds
        assert c.symbol not in {"BDNF", "CREB1", "NTRK2", "GRIN2B", "CAMK2A", "ARC"}


def test_gene_pathway_candidates_are_sorted_by_real_distance() -> None:
    reports = build_gene_pathway_candidates()
    for report in reports:
        distances = [c.distance_fraction for c in report.candidates]
        assert distances == sorted(distances)
        assert all(d >= 0 for d in distances)


def test_gene_pathway_candidates_endpoint_returns_honesty_note() -> None:
    response = client.get("/api/lab/gene-pathway-candidates")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 6
    for report in body:
        assert "근접" in report["honesty_note"] or "관련" in report["honesty_note"]
