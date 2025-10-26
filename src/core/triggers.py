from __future__ import annotations
import re
from typing import Dict, List, Set, Tuple
from .config import Config, Trigger


class TriggerMatcher:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.compiled: List[Tuple[Trigger, re.Pattern]] = []
        for tr in cfg.triggers:
            flags = 0
            for f in tr.flags:
                if f.lower() == 'i': flags |= re.IGNORECASE
                if f.lower() == 'm': flags |= re.MULTILINE
                if f.lower() == 's': flags |= re.DOTALL
            pat = re.compile(tr.pattern, flags)
            self.compiled.append((tr, pat))

    def extract(self, text: str) -> Set[str]:
        events: Set[str] = set()
        for tr, pat in self.compiled:
            if pat.search(text or ""):
                events.add(tr.event)
        return events

    def get_matches(self, text: str) -> Dict[str, List[str]]:
        events_matches = {}
        for tr, pat in self.compiled:
            matches = []
            for match in pat.finditer(text or ""):
                matches.append(match.group(0))
            if matches:
                events_matches[tr.event] = matches
        return events_matches

    def weight_of(self, event: str) -> int:
        return next((t.weight for t, _ in self.compiled if t.event == event), 0)
