"""Skill cards and the four characters' five-card starter decks."""

from __future__ import annotations

from dataclasses import dataclass, replace


PLAYER_CARD_DAMAGE_SCALE = 0.5
MAX_DECK_SIZE = 9


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
    hit_count: int = 1
    stop_on_miss: bool = False
    hold_to_judge: bool = False
    effect_key: str | None = None

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
        if self.effect_key:
            return {
                "adeline_double_slash": "연격",
                "neira_spin": "속도",
                "neira_focus": "홀드",
                "neira_triple_assault": "연격",
                "lumiel_heal": "회복",
                "lumiel_guard": "보호",
                "lumiel_draw": "드로우",
                "karmina_twin_slash": "출혈",
                "karmina_assault": "기절",
                "karmina_karma": "중첩 강화",
            }.get(self.effect_key, "공격")
        return "공격"


def starter_deck(character_id: str) -> list[SkillCard]:
    """Each 5-card deck shares one basic strike and four thematic skills."""
    # card_balance.md damage coefficients are doubled so the global scale
    # below restores the intended in-combat multipliers exactly once.
    basic = SkillCard("공격", "기본 공격", power=1.0)
    decks = {
        "A": [
            SkillCard("정밀 타격", "느린 속도\n약간 좁은 판정", 1.4, 0.8, 0.045, 0.15),
            SkillCard(
                "연속 베기", "2회 판정\n모두 PERFECT면 취약 부여", 0.76, 1.1, 0.045, 0.15,
                hit_count=2, effect_key="adeline_double_slash",
            ),
            SkillCard(
                "제압", "GOOD 이상이면 적 둔화", 0.9, 1.1, 0.055, 0.17,
                status_key="slow", status_amount=18, status_turns=2,
            ),
            SkillCard("빈틈 찌르기", "홀드형 공격", 1.7, 1.2, 0.035, 0.12, hold_to_judge=True),
        ],
        "B": [
            SkillCard("급소 찌르기", "높은 피해\n좁은 판정", 1.5, 1.1, 0.035, 0.12),
            SkillCard("회전 베기", "PERFECT면 속도 증가", 1.6, 1.2, 0.055, 0.17, effect_key="neira_spin"),
            SkillCard("집중", "다음 공격 게이지 감속", 1.2, 1.0, 0.045, 0.15, hold_to_judge=True, effect_key="neira_focus"),
            SkillCard(
                "삼연 암습", "연속 피해 증가", 0.6, 1.2, 0.035, 0.12,
                hit_count=3, stop_on_miss=True, effect_key="neira_triple_assault",
            ),
        ],
        "C": [
            SkillCard("광휘", "약간 빠른 일반 공격", 1.3, 1.1, 0.055, 0.17),
            SkillCard("치유의 파동", "가한 피해의 40%만큼 최저 체력 아군 회복", 0.5, 0.9, 0.045, 0.15, effect_key="lumiel_heal"),
            SkillCard("수호의 타종", "이번 턴 동안 자신 외 아군 피해 감소", 0.6, 1.0, 0.075, 0.21, effect_key="lumiel_guard"),
            SkillCard("순환의 노래", "GOOD 이상이면 카드 1장 드로우", 0.84, 0.8, 0.055, 0.17, effect_key="lumiel_draw"),
        ],
        "D": [
            SkillCard("흐름 베기", "빠르고 넓은 판정", 0.8, 1.1, 0.075, 0.21),
            SkillCard(
                "쌍섬", "GOOD 이상 적중마다 출혈", 0.7, 1.2, 0.055, 0.17,
                hit_count=2, effect_key="karmina_twin_slash",
            ),
            SkillCard("강습", "PERFECT면 기절", 1.32, 1.2, 0.035, 0.12, hold_to_judge=True, effect_key="karmina_assault"),
            SkillCard("카르마", "이번 공격의 PERFECT 중첩 효과 1.5배", 1.0, 1.1, 0.055, 0.17, effect_key="karmina_karma"),
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
    floor_two_skills = {
        "frost_sentinel": [
            SkillCard("서리 인장", "방어 실패 시 둔화", 0.88, 1.38, status_key="slow", status_amount=18, status_turns=2),
            SkillCard("빙결 돌진", "느리고 강한 공격", 1.2, 0.88),
        ],
        "ember_stalker": [
            SkillCard("잔불 물기", "방어 실패 시 출혈", 0.86, 1.48, status_key="bleed", status_amount=8, status_turns=2),
            SkillCard("화염 급습", "빠른 공격", 1.14, 1.16),
        ],
        "rune_duelist": [
            SkillCard("룬 파쇄", "방어 실패 시 쇠약", 0.9, 1.32, status_key="weak", status_amount=0.18),
            SkillCard("세 겹 칼날", "무거운 공격", 1.2, 0.98),
        ],
        "mist_archer": [
            SkillCard("흐린 표식", "방어 실패 시 취약", 0.84, 1.42, status_key="vulnerable", status_amount=0.18),
            SkillCard("안개 화살", "빠르고 강한 공격", 1.18, 1.08),
        ],
        "iron_watcher": [
            SkillCard("구속의 망치", "방어 실패 시 강박", 0.9, 1.22, status_key="rest_lock", status_turns=2),
            SkillCard("강철 낙하", "느리고 강한 공격", 1.24, 0.9),
        ],
        "storm_hound": [
            SkillCard("폭풍 돌진", "빠르고 강한 공격", 1.2, 1.28),
            SkillCard("질풍 발톱", "방어 실패 시 둔화", 0.88, 1.62, status_key="slow", status_amount=16, status_turns=2),
        ],
        "thorn_custodian": [
            SkillCard("가시 감옥", "방어 실패 시 강박", 0.92, 1.28, status_key="rest_lock", status_turns=2),
            SkillCard("찔레 파열", "방어 실패 시 출혈", 1.18, 0.94, status_key="bleed", status_amount=10, status_turns=2),
            SkillCard("뿌리 내리치기", "느리고 강한 공격", 1.34, 0.8),
        ],
        "rune_reaper": [
            SkillCard("기록 절단", "방어 실패 시 쇠약", 0.96, 1.48, status_key="weak", status_amount=0.2),
            SkillCard("룬 붕괴", "느리고 강한 공격", 1.34, 0.84),
            SkillCard("문장 흡수", "방어 실패 시 취약", 0.9, 1.3, status_key="vulnerable", status_amount=0.2),
        ],
        "frost_champion": [
            SkillCard("빙결 검무", "방어 실패 시 둔화", 1.0, 1.26, status_key="slow", status_amount=20, status_turns=2),
            SkillCard("서리 파열", "방어 실패 시 기절", 1.24, 0.9, status_key="stun"),
            SkillCard("빙하 단죄", "느리고 강한 공격", 1.42, 0.78),
        ],
        "veil_archivist": [
            SkillCard("기억 봉인", "방어 실패 시 강박", 0.94, 1.5, status_key="rest_lock", status_turns=2),
            SkillCard("균열 기록", "방어 실패 시 취약", 1.08, 1.22, status_key="vulnerable", status_amount=0.22),
            SkillCard("회랑 종언", "느리고 강한 보스 공격", 1.48, 0.82),
        ],
    }
    if enemy_id in floor_two_skills:
        return floor_two_skills[enemy_id]
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
        SkillCard("압박 포효", "PERFECT 적중 시 강박", 1.0, 1.6, status_key="rest_lock", status_amount=0, status_turns=2),
        SkillCard("그림자 습격", "빠른 공격", 0.9, 2.0),
    ]
