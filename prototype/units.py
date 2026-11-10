"""Combat units for the battle screen."""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from cards import SkillCard, enemy_skills, starter_deck
from status_effects import StatusCollection


CHARACTER_DATA = {
    "A": {"name": "A · 정밀 기사", "hp": 100, "attack": 100, "speed": 100, "accent": (106, 200, 185), "trait": "입력 판정 구간이 넓음"},
    "B": {"name": "B · 회피 검사", "hp": 80, "attack": 110, "speed": 105, "accent": (116, 175, 226), "trait": "방어 PERFECT 시 피해 회피"},
    "C": {"name": "C · 비전 기록자", "hp": 130, "attack": 90, "speed": 80, "accent": (185, 147, 224), "trait": "휴식 시 카드 1장 추가"},
    "D": {"name": "D · 연쇄 검희", "hp": 90, "attack": 115, "speed": 120, "accent": (229, 173, 111), "trait": "PERFECT마다 공격력 중첩"},
}


def character_info(character_id: str) -> dict:
    return CHARACTER_DATA[character_id]


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


def create_party(character_ids: list[str] | None = None) -> list[PlayerCharacter]:
    selected_ids = character_ids if character_ids is not None else list(CHARACTER_DATA)
    party: list[PlayerCharacter] = []
    for character_id in selected_ids:
        data = character_info(character_id)
        character = PlayerCharacter(
            unit_id=character_id,
            name=data["name"],
            side="player",
            hp=data["hp"],
            max_hp=data["hp"],
            attack=data["attack"],
            speed=data["speed"],
            accent=data["accent"],
            trait_text=data["trait"],
            deck=starter_deck(character_id),
        )
        random.shuffle(character.deck)
        character.draw(3)
        party.append(character)
    return party


def create_enemies(encounter_id: str = "corridor") -> list[Enemy]:
    if encounter_id == "floor1_boss":
        return [
            Enemy(
                unit_id="floor1_guardian",
                name="1층 회랑의 감시자",
                side="enemy",
                hp=235,
                max_hp=235,
                attack=23,
                speed=108,
                accent=(217, 167, 108),
                skills=enemy_skills("floor1_guardian"),
            )
        ]
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
