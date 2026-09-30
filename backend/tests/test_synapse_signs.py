"""시냅스 부호 규칙 테스트 (docs/47). 수용체 기반 부호(Fenyves et al. 2020 예측)는 가상 웜 폐루프만
선택적으로 쓰고, 기존 기능의 기본 규칙(GABA만 억제성)은 그대로여야 한다."""

from app.domain.schemas import Neurotransmitter
from app.simulation.hh_model import _is_inhibitory, _receptor_predicted_signs


def test_default_rule_is_unchanged_gaba_only() -> None:
    assert _is_inhibitory("AWCL", "AIYL", Neurotransmitter.GLUTAMATE, "gaba_only") is False
    assert _is_inhibitory("DD1", "VB2", Neurotransmitter.GABA, "gaba_only") is True


def test_receptor_predicted_rule_matches_known_glucl_inhibition() -> None:
    # Chalasani et al. 2007: AWC -> AIY는 글루탐산 개폐 염소채널(GLC-3)을 통한 억제, AWC -> AIB는 흥분
    signs = _receptor_predicted_signs()
    assert signs["AWCL>AIYL"] == "-"
    assert signs["AWCL>AIBL"] == "+"
    assert _is_inhibitory("AWCL", "AIYL", Neurotransmitter.GLUTAMATE, "receptor_predicted") is True
    assert _is_inhibitory("AWCL", "AIBL", Neurotransmitter.GLUTAMATE, "receptor_predicted") is False


def test_unresolved_predictions_fall_back_to_the_default_rule_instead_of_guessing() -> None:
    signs = _receptor_predicted_signs()
    complex_edge = next(k for k, v in signs.items() if v == "complex")
    pre, post = complex_edge.split(">")
    assert _is_inhibitory(pre, post, Neurotransmitter.GLUTAMATE, "receptor_predicted") is False
    assert _is_inhibitory("NOT_A_NEURON", "ALSO_NOT", Neurotransmitter.GABA, "receptor_predicted") is True
