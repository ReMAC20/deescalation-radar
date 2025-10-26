from __future__ import annotations
from typing import Dict


class CoolingManager:
    def __init__(self):
        self.neutral_counts: Dict[str, int] = {}

    def update_count(self, chat_id: str, current_state: str, next_state: str, events: Set[str]) -> str:
        if events:
            self.neutral_counts[chat_id] = 0
            return next_state

        if current_state in ["HEATED", "TENSE", "REPAIRED"]:
            count = self.neutral_counts[chat_id] + 1
            self.neutral_counts[chat_id] = count

            if current_state == "HEATED" and count >= 3:
                self.neutral_counts[chat_id] = 0
                return "TENSE"

            elif current_state == "TENSE" and count >= 3:
                self.neutral_counts[chat_id] = 0
                return "NEUTRAL"

            elif current_state == "REPAIRED" and count >= 1:
                self.neutral_counts[chat_id] = 0
                return "NEUTRAL"

        return next_state
