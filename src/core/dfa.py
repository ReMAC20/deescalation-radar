from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Set
from .config import Config, DFATransition


@dataclass
class DFAState:
    name: str


class DFAEngine:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.states = cfg.dfa_states
        self.start_state = cfg.dfa_start
        self.transitions: List[DFATransition] = cfg.dfa_transitions

    def step(self, current: str, events: Set[str]) -> str:
        high_priority_events = {"INSULT", "THREAT", "ALL_CAPS", "PROVOCATION",
                                "ACCUSATION", "SARCASTIC", "INTERRUPT", "BLAME_YOU"}
        low_priority_events = {"APOLOGY", "EMPATHY", "SOFTENER", "THANKS",
                               "ACKNOWLEDGE", "OFFER_PAUSE"}

        for t in self.transitions:
            if t.from_state != current:
                continue
            if t.when_any_of and any(e in high_priority_events and e in events for e in t.when_any_of):
                return t.to_state

        for t in self.transitions:
            if t.from_state != current:
                continue
            if t.when_any_of and any(e in low_priority_events and e in events for e in t.when_any_of):
                return t.to_state

        for t in self.transitions:
            if t.from_state != current:
                continue
            if t.otherwise:
                return t.to_state

        return current
