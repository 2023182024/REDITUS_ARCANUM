"""Skill cards and the four characters' five-card starter decks."""

from __future__ import annotations

from dataclasses import dataclass, replace


PLAYER_CARD_DAMAGE_SCALE = 0.5


@dataclass
class SkillCard:
    name: str
    description: str
    power: float = 1.0
    timing_speed: float = 1.0
    perfect_window: float = 0.055
    good_window: float = 0.17
    status_key: str | None = None
    status_amount: float = 0
    status_turns: int = 1

    def short_effect(self) -> str:
        if self.status_key:
            return {
                "bleed": "출혈",
                "weak": "쇠약",
                "slow": "둔화",
                "stun": "기절",
                "vulnerable": "취약",
                "rest_lock": "강박",
            }[self.status_key]
        return "공격"


def starter_deck(character_id: str) -> list[SkillCard]:
    """Each 5-card deck shares one basic strike and four thematic skills."""
    basic = SkillCard("기본 베기", "안정적인 기본 공격", power=1.0, timing_speed=1.15)
    decks = {
        "A": [
            SkillCard("정밀 타격", "판정 구간이 넓은 공격", 1.08, 0.88, 0.095, 0.22),
            SkillCard("견제", "적의 공격을 약화", 0.8, 1.3, status_key="weak", status_amount=0.22),
            SkillCard("균형 베기", "빠르게 입력하는 공격", 0.92, 1.8, 0.045, 0.14),
            SkillCard("틈새 찌르기", "적을 둔화", 0.9, 1.0, status_key="slow", status_amount=18, status_turns=2),
        ],
        "B": [
            SkillCard("급소 찌르기", "적에게 출혈을 부여", 1.08, 1.55, status_key="bleed", status_amount=6, status_turns=2),
            SkillCard("회전 베기", "연속된 빠른 타격", 0.95, 2.1, 0.05, 0.15),
            SkillCard("발목 베기", "적의 속도를 낮춤", 0.82, 1.05, status_key="slow", status_amount=20, status_turns=2),
            SkillCard("집중", "넓은 타이밍 구간", 0.88, 0.72, 0.085, 0.2),
        ],
        "C": [
            SkillCard("노출 마법", "다음 피격 피해 증가", 0.82, 0.9, status_key="vulnerable", status_amount=0.25, status_turns=1),
            SkillCard("비전 화살", "위력 있는 마법 공격", 1.2, 1.28, 0.045, 0.15),
            SkillCard("약화 주문", "적의 공격력을 낮춤", 0.75, 1.0, status_key="weak", status_amount=0.25),
            SkillCard("빙결 파편", "적의 속도를 낮춤", 0.9, 1.4, status_key="slow", status_amount=16, status_turns=2),
        ],
        "D": [
            SkillCard("연쇄 베기", "퍼펙트 시 출혈 부여", 1.05, 1.75, 0.045, 0.14, "bleed", 7, 2),
            SkillCard("제압 공격", "퍼펙트 시 적을 기절", 0.88, 1.2, 0.05, 0.15, "stun", 0, 1),
            SkillCard("강습", "느리지만 강력한 공격", 1.35, 0.72, 0.035, 0.12),
            SkillCard("연속 타격", "빠른 연속 공격", 0.92, 2.35, 0.04, 0.13),
        ],
    }
    player_cards = [basic, *decks[character_id]]
    for card in player_cards:
        card.power *= PLAYER_CARD_DAMAGE_SCALE
    return player_cards


def player_reward_card(enemy_skill: SkillCard) -> SkillCard:
    """Copy an enemy skill into a player deck at normal player-card damage scale."""
    return replace(enemy_skill, power=enemy_skill.power * PLAYER_CARD_DAMAGE_SCALE)


def enemy_skills(enemy_id: str) -> list[SkillCard]:
    if enemy_id == "floor1_guardian":
        return [
            SkillCard("회랑 강타", "무거운 보스 공격", 1.28, 0.82),
            SkillCard("봉인 파동", "적중 시 쇠약", 1.0, 1.35, status_key="weak", status_amount=0.2),
        ]
    if enemy_id == "glass_wraith":
        return [
            SkillCard("유리 파편", "적중 시 쇠약", 1.0, 1.35, status_key="weak", status_amount=0.18),
            SkillCard("균열탄", "느리고 무거운 공격", 1.15, 0.88),
        ]
    return [
        SkillCard("압박 포효", "PERFECT 적중 시 휴식 불가", 1.0, 1.6, status_key="rest_lock", status_amount=0, status_turns=2),
        SkillCard("그림자 습격", "빠른 공격", 0.9, 2.0),
    ]
