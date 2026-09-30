from fastapi import APIRouter

from app.data.celegans_connectome import get_classic_ablations, get_connectome
from app.domain.schemas import ClassicAblation, Connectome

router = APIRouter(tags=["connectome"])


@router.get("/api/connectome", response_model=Connectome)
def read_connectome() -> Connectome:
    return get_connectome()


@router.get("/api/classic-ablations", response_model=list[ClassicAblation])
def read_classic_ablations() -> list[ClassicAblation]:
    return get_classic_ablations()
