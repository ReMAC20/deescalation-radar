from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import yaml, re


@dataclass
class Trigger:
    name: str
    description: str
    pattern: str
    flags: List[str]
    event: str
    weight: int = 0


@dataclass
class DFATransition:
    from_state: str
    to_state: str
    when_any_of: Optional[List[str]] = None
    otherwise: bool = False


@dataclass
class RiskConfig:
    base_by_state: Dict[str, int]
    decay_per_step: int
    cap: int
    event_weights_override: Dict[str, int] = field(default_factory=dict)


@dataclass
class Config:
    triggers: List[Trigger]
    labels: Dict[str, List[str]]
    risk: RiskConfig
    dfa_states: List[str]
    dfa_start: str
    dfa_transitions: List[DFATransition]
    ltlf_predicates: Dict[str, str]
    ltlf_rules: List[Dict[str, Any]]
    hints: Dict[str, Any]
    extraction: Dict[str, Any]

    @staticmethod
    def from_yaml(path: str) -> 'Config':
        with open(path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        triggers = [Trigger(**t) for t in data['triggers']]
        trans = []
        for t in data['dfa']['transitions']:
            trans.append(DFATransition(
                from_state=t['from'],
                to_state=t['to'],
                when_any_of=t.get('when_any_of'),
                otherwise=t.get('otherwise', False)
            ))
        risk = RiskConfig(**data['risk'])
        cfg = Config(
            triggers=triggers,
            labels=data['labels'],
            risk=risk,
            dfa_states=data['dfa']['states'],
            dfa_start=data['dfa']['start_state'],
            dfa_transitions=trans,
            ltlf_predicates=data['ltlf']['predicates'],
            ltlf_rules=data['ltlf']['rules'],
            hints=data.get('hints', {}),
            extraction=data.get('event_extraction', {}),
        )
        return cfg
