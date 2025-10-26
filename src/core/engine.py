from __future__ import annotations
from typing import Dict, Any, Set, List, Tuple
from dataclasses import dataclass, field
from .config import Config
from .triggers import TriggerMatcher
from .dfa import DFAEngine
from .risk import RiskMeter
from .ltlf import parse_formula, eval_formula, build_trace_from_steps
from .hints import pick_hints
from .cooling import CoolingManager


@dataclass
class ChatState:
    state: str
    risk: int = 0
    history: List[Dict[str, Any]] = field(default_factory=list)


class RulesEngine:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.triggers = TriggerMatcher(cfg)
        self.dfa = DFAEngine(cfg)
        self.chats: Dict[str, ChatState] = {}
        self.risk_meters: Dict[str, RiskMeter] = {}
        self.cooling_mgr = CoolingManager()
        self.ltlf_rules = [(r['id'], r['description'], parse_formula(r['formula'])) for r in cfg.ltlf_rules]

    def get_chat(self, chat_id: str) -> ChatState:
        cs = self.chats.get(chat_id)
        if cs is None:
            cs = ChatState(state=self.cfg.dfa_start, risk=0, history=[])
            self.chats[chat_id] = cs
            self.risk_meters[chat_id] = RiskMeter(self.cfg, self.triggers)
        return cs

    def process_message(self, chat_id: str, text: str) -> Dict[str, Any]:
        cs = self.get_chat(chat_id)
        events: Set[str] = self.triggers.extract(text)
        raw_next_state = self.dfa.step(cs.state, events)

        final_next_state = self.cooling_mgr.update_count(chat_id, cs.state, raw_next_state, events)
        risk = self.risk_meters[chat_id].update(final_next_state, events)

        step = {'events': sorted(list(events)), 'state': final_next_state}
        cs.history.append(step)
        cs.state = final_next_state
        cs.risk = risk

        hints = pick_hints(self.cfg, self.triggers, text, final_next_state, events)
        trace = build_trace_from_steps(cs.history)
        ltlf_results = []
        for rid, desc, node in self.ltlf_rules:
            ok = eval_formula(node, trace, 0)
            ltlf_results.append({'id': rid, 'ok': ok, 'description': desc})

        return {
            'state': final_next_state,
            'risk': risk,
            'events': sorted(list(events)),
            'ltlf': ltlf_results,
            'hints': hints,
        }
