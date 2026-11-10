"""Combat units for the battle screen."""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from cards import SkillCard, enemy_skills, starter_deck
from status_effects import StatusCollection


@dataclass
class Combatant:
    unit_id: str
    name: str
    side: str
    hp: int
    max_hp: int
    attack: int
    speed: int
    accent: tuple[int, int, int]
    statuses: StatusCollection = field(default_factory=StatusCollection)
    rested: bool = False
    alive: bool = True

    def effective_speed(self) -> int:
        slow = self.statuses.get("slow")
        return max(1, self.speed - int(slow.amount)) if slow else self.speed

    def receive_hit(self, damage: float) -> int:
        vulnerable = self.statuses.consume("vulnerable")
        if vulnerable:
            damage *= 1 + vulnerable.amount
        amount = max(1, round(damage))
        self.hp = max(0, self.hp - amount)
        self.alive = self.hp > 0
        return amount


@dataclass
class PlayerCharacter(Combatant):
    trait_text: str = ""
    deck: list[SkillCard] = field(default_factory=list)
    hand: list[SkillCard] = field(default_factory=list)
    discard: list[SkillCard] = field(default_factory=list)
    perfect_stacks: int = 0

    def draw(self, count: int) -> int:
        drawn = 0
        for _ in range(count):
            if len(self.hand) >= 5:
                break
            if not self.deck and self.discard:
                self.deck, self.discard = self.discard, []
                random.shuffle(self.deck)
            if not self.deck:
                break
            self.hand.append(self.deck.pop())
            drawn += 1
        return drawn

    def make_discard(self, card: SkillCard) -> None:
        self.discard.append(card)


@dataclass
class Enemy(Combatant):
    skills: list[SkillCard] = field(default_factory=list)
    attacks_made: int = 0

    def choose_skill(self) -> SkillCard:
        self.attacks_made += 1
        return random.choice(self.skills)


def create_party() -> list[PlayerCharacter]:
    setup = [
        ("A", "A · 정밀 기사", 100, 100, 100, (106, 200, 185), "입력 판정 구간이 넓음"),
        ("B", "B · 회피 검사", 80, 110, 105, (116, 175, 226), "방어 PERFECT 시 피해 회피"),
        ("C", "C · 비전 기록자", 130, 90, 80, (185, 147, 224), "휴식 시 카드 1장 추가"),
        ("D", "D · 연쇄 검희", 90, 115, 120, (229, 173, 111), "PERFECT마다 공격력 중첩"),
    ]
    party: list[PlayerCharacter] = []
    for character_id, name, hp, attack, speed, accent, trait in setup:
        character = PlayerCharacter(
            unit_id=character_id,
            name=name,
            side="player",
            hp=hp,
            max_hp=hp,
            attack=attack,
            speed=speed,
            accent=accent,
            trait_text=trait,
            deck=starter_deck(character_id),
        )
        random.shuffle(character.deck)
        character.draw(3)
        party.append(character)
    return party


def create_enemies() -> list[Enemy]:
    return [
        Enemy(
            unit_id="glass_wraith",
            name="유리 망령",
            side="enemy",
            hp=118,
            max_hp=118,
            attack=16,
            speed=112,
            accent=(186, 119, 194),
            skills=enemy_skills("glass_wraith"),
        ),
        Enemy(
            unit_id="ash_hound",
            name="잿빛 늑대",
            side="enemy",
            hp=132,
            max_hp=132,
            attack=14,
            speed=91,
            accent=(218, 130, 95),
            skills=enemy_skills("ash_hound"),
        ),
    ]
