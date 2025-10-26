from __future__ import annotations
from typing import Set
from .config import Config
from .triggers import TriggerMatcher


class RiskMeter:
    def __init__(self, cfg: Config, triggers: TriggerMatcher):
        self.cfg = cfg
        self.triggers = triggers
        self.value = 0

    def update(self, state: str, events: Set[str]) -> int:
        self.value = max(0, self.value - self.cfg.risk.decay_per_step)

        base = self.cfg.risk.base_by_state.get(state, 0)
        self.value += base

        for e in events:
            w = self.cfg.risk.event_weights_override.get(e, self.triggers.weight_of(e))
            self.value += w

        self.value = min(self.cfg.risk.cap, self.value)
        return self.value
