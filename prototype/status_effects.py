"""Status effects used by the REDITUS ARCANUM battle prototype."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class StatusEffect:
    key: str
    turns: int = 1
    amount: float = 0
    hits: int = 0

    @property
    def label(self) -> str:
        return {
            "bleed": "출혈",
            "weak": "쇠약",
            "slow": "둔화",
            "stun": "기절",
            "vulnerable": "취약",
            "rest_lock": "강박",
        }[self.key]

    def display(self) -> str:
        details = {
            "bleed": f"{int(self.amount)} · {self.turns}T",
            "weak": f"-{int(self.amount * 100)}%",
            "slow": f"-{int(self.amount)} SPD",
            "stun": "다음 행동 불가",
            "vulnerable": f"+{int(self.amount * 100)}% · {self.hits}회",
            "rest_lock": f"휴식 불가 · {self.turns}T",
        }
        return f"{self.label} {details[self.key]}"


class StatusCollection:
    """Small, explicit status container so the battle rules stay easy to tune."""

    def __init__(self) -> None:
        self.effects: dict[str, StatusEffect] = {}

    def get(self, key: str) -> StatusEffect | None:
        return self.effects.get(key)

    def has(self, key: str) -> bool:
        return key in self.effects

    def apply(self, key: str, turns: int = 1, amount: float = 0, hits: int = 0) -> None:
        old = self.effects.get(key)
        if key == "bleed" and old:
            old.amount += amount
            old.turns = max(old.turns, turns)
            return
        if key == "vulnerable":
            self.effects[key] = StatusEffect(key, turns=1, amount=amount, hits=max(1, hits))
            return
        if old:
            old.turns = max(old.turns, turns)
            old.amount = max(old.amount, amount)
            return
        self.effects[key] = StatusEffect(key, turns=turns, amount=amount, hits=hits)

    def consume(self, key: str) -> StatusEffect | None:
        return self.effects.pop(key, None)

    def rest_tick(self) -> list[str]:
        """Rest shortens timed effects without triggering their effect."""
        removed: list[str] = []
        for key in ("bleed", "slow", "rest_lock"):
            effect = self.effects.get(key)
            if effect:
                effect.turns -= 1
                if effect.turns <= 0:
                    self.effects.pop(key, None)
                    removed.append(key)
        return removed

    def end_round(self) -> tuple[int, list[str]]:
        """Apply end-of-round effects and age the effects with durations."""
        bleed_damage = 0
        removed: list[str] = []
        for key in ("bleed", "slow", "rest_lock"):
            effect = self.effects.get(key)
            if not effect:
                continue
            if key == "bleed":
                bleed_damage += int(effect.amount)
            effect.turns -= 1
            if effect.turns <= 0:
                self.effects.pop(key, None)
                removed.append(key)
        return bleed_damage, removed

    def snapshot(self) -> list[StatusEffect]:
        return list(self.effects.values())
