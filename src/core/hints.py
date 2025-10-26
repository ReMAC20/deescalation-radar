from __future__ import annotations
from typing import List, Dict, Set, Optional
import random
import re
from .triggers import TriggerMatcher


def pick_hints(cfg, trigger_matcher: TriggerMatcher, text: str, state: str, events: Set[str], count: int = 2,
               user: str = None, message: str = None) -> List[str]:
    res: List[str] = []

    events_matches = trigger_matcher.get_matches(text)

    for event in events:
        event_hints = (cfg.hints.get('on_events') or {}).get(event) or []

        matches = events_matches.get(event, [])

        if matches:
            match_text = matches[0] if matches else ""

            for hint_template in event_hints:
                personalized_hint = hint_template
                if '{match}' in personalized_hint:
                    personalized_hint = personalized_hint.replace('{match}', f'"{match_text}"')
                if '{user}' in personalized_hint and user:
                    personalized_hint = personalized_hint.replace('{user}', user)
                if '{message}' in personalized_hint and message:
                    m_snip = (message[:200] + '...') if len(message) > 200 else message
                    personalized_hint = personalized_hint.replace('{message}', m_snip)
                res.append(personalized_hint)
        else:
            res.extend(event_hints)

    state_hints = (cfg.hints.get('on_states') or {}).get(state) or []
    res.extend(state_hints)

    seen = set()
    uniq = [x for x in res if not (x in seen or seen.add(x))]
    if not uniq:
        return []

    random.shuffle(uniq)
    return uniq[:count]
