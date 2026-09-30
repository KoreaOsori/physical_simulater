"""가상 웜/초파리 폐루프가 공유하는 기록(궤적·통계) 도우미 (docs/45).

두 모듈의 신경 메커니즘은 종마다 다른 실제 문헌에 따로 근거하므로 합치지
않았다 -- 여기엔 종과 무관한 "기록" 부분만 둔다."""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass

from brian2 import NetworkOperation, Quantity, ms, nA

from app.lab.schemas import VirtualOrganismStatsOut

MAX_TRAIL_POINTS = 1500

_run_ids = itertools.count(1)


def next_run_id() -> int:
    return next(_run_ids)


class StaleRunError(Exception):
    """수동 조종 위치가 이미 끝난 기록(다시 시작 이전)의 것일 때 -- 라우트에서 409."""


MAX_REFLEX_BACK_FRACTION = 0.5  # 반사 후진 거리 = 한 틱 이동거리의 이 비율 -- docs/41/42의 손튜닝 관행 그대로


@dataclass
class EpisodeStats:
    """한 기록 구간(다시 시작 또는 냄새원을 옮긴 시점부터)의 통계."""

    start_bio_ms: float = 0.0
    bio_ms: float = 0.0
    distance_um: float = 0.0
    auto_ticks: int = 0
    manual_ticks: int = 0
    reorient_decisions: int = 0
    closest_um: float = math.inf
    reached_at_ms: float | None = None

    def restart(self, closest_um: float) -> None:
        self.start_bio_ms = self.bio_ms
        self.distance_um = 0.0
        self.auto_ticks = 0
        self.manual_ticks = 0
        self.reorient_decisions = 0
        self.closest_um = closest_um
        self.reached_at_ms = None

    def to_out(self) -> VirtualOrganismStatsOut:
        return VirtualOrganismStatsOut(
            bio_time_s=(self.bio_ms - self.start_bio_ms) / 1000.0,
            distance_mm=self.distance_um / 1000.0,
            auto_ticks=self.auto_ticks,
            manual_ticks=self.manual_ticks,
            reorient_decisions=self.reorient_decisions,
            closest_approach_mm=(self.closest_um if math.isfinite(self.closest_um) else 0.0) / 1000.0,
            reached_at_s=None if self.reached_at_ms is None else (self.reached_at_ms - self.start_bio_ms) / 1000.0,
        )


def extend_trail(trail: list[list[float]], points: list[list[float]]) -> float:
    """경로 점을 덧붙이고 상한을 넘으면 오래된 쪽을 버린다. 이동거리(μm)를 돌려준다."""
    moved = 0.0
    for p in points:
        if len(p) < 2:
            continue
        x, y = float(p[0]), float(p[1])
        if trail:
            moved += math.hypot(x - trail[-1][0], y - trail[-1][1])
        trail.append([x, y])
    if len(trail) > MAX_TRAIL_POINTS:
        del trail[: len(trail) - MAX_TRAIL_POINTS]
    return moved


def clamp_to_disc(x_um: float, y_um: float, radius_um: float) -> tuple[float, float]:
    r = math.hypot(x_um, y_um)
    if r <= radius_um:
        return x_um, y_um
    s = radius_um / r
    return x_um * s, y_um * s


class StimulusSwitch:
    """한 틱을 `net.run()` 한 번으로 돌리기 위한 자극 스위치(docs/45 성능 수정).

    원래는 틱마다 run(20ms 자극) + run(80ms 휴지)로 두 번 돌렸는데, Brian2는 run()을
    부를 때마다 코드 객체를 다시 해시하고 gc.collect를 해서(실측: run당 ~1.2초, 시뮬레이션
    자체와 비슷한 비용) 틱 비용이 거의 두 배였다. 네트워크 생성 직후 한 번, 20ms마다 도는
    NetworkOperation을 넣어 t>=자극 구간 끝에서 전류를 0으로 끄게 하면 같은 자극 파형을
    run() 한 번으로 얻는다(결과가 기존 방식과 스파이크 단위로 같은지 직접 비교 확인).
    NetworkOperation(dt=...)는 자기 전용 Clock을 새로 만든다 -- docs/42의 공유 Clock
    버그를 다시 들이지 않는다."""

    def __init__(self, assets, stim_ms: float) -> None:
        self._assets = assets
        self._stim_end = stim_ms * ms
        self.indices: list[int] = []
        op = NetworkOperation(self._maybe_switch_off, dt=stim_ms * ms, when="start")
        assets.net.add(op)
        assets.net.store("initial")  # 아직 한 번도 돌지 않았으므로 t=0 스냅샷을 새 구성으로 다시 저장

    def _maybe_switch_off(self, t: Quantity) -> None:
        if self.indices and t >= self._stim_end:
            for idx in self.indices:
                self._assets.group.I[idx] = 0 * nA
            self.indices = []

    def run_tick(self, indices: list[int], current, tick_ms: float) -> None:
        self.run_tick_currents({idx: current for idx in indices}, tick_ms)

    def run_tick_currents(self, currents: dict, tick_ms: float) -> None:
        """뉴런마다 다른 자극 전류(예: ON 세포와 OFF 세포, docs/47)로 한 틱."""
        net = self._assets.net
        net.restore("initial")
        self.indices = list(currents)
        for idx, cur in currents.items():
            self._assets.group.I[idx] = cur
        net.run(tick_ms * ms)
        for idx in currents:  # 안전장치 -- 틱 끝엔 항상 0
            self._assets.group.I[idx] = 0 * nA
        self.indices = []
