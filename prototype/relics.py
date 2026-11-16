"""Party-wide relic data sourced from papers/relics.md."""

from __future__ import annotations

from dataclasses import dataclass


MAX_RELICS = 4


@dataclass(frozen=True)
class Relic:
    relic_id: str
    name: str
    description: str


RELICS = (
    Relic("precision_clock", "정밀한 시계", "PERFECT 공격 피해량 +10%"),
    Relic("focus_crystal", "집중의 수정", "PERFECT 방어 성공 시 다음 공격 피해량 +10%"),
    Relic("old_pen", "낡은 만년필", "휴식 시 손패가 비어 있지 않으면 10% 확률로 카드 1장 추가 드로우"),
    Relic("cycle_compass", "순환의 나침반", "전투 중 처음 손패가 소진될 때 카드 1장 추가 드로우"),
    Relic("first_strike_charm", "선공자의 부적", "가장 먼저 행동하는 아군의 첫 공격 피해량 +15%"),
    Relic("life_crystal", "생명의 수정", "아군이 처음으로 체력 30% 이하가 되면 최대 체력의 30% 회복"),
    Relic("immortal_goblet", "불멸의 성배", "전투당 최초의 치명타를 체력 1로 버티고 최대 체력의 10% 회복"),
    Relic("warrior_insignia", "전사의 휘장", "체력이 50% 이상인 적에게 주는 피해 +10%"),
    Relic("hunter_insignia", "사냥꾼의 휘장", "체력이 50% 이하인 적에게 주는 피해 +10%"),
    Relic("counter_bell", "반격의 종", "PERFECT 방어 성공 시 받은 피해의 30% 반사"),
    Relic("gale_compass", "질풍의 나침반", "PERFECT 공격 성공 시 다음 턴 속도 +10%"),
    Relic("clockwork", "태엽 장치", "전투에서 처음 적을 처치한 아군이 추가 행동 1회"),
    Relic("time_shard", "시간의 파편", "처음 체력 30% 이하가 된 아군이 추가 행동 1회"),
    Relic("fortune_coin", "운명의 동전", "첫 턴에 무작위 아군에게 추가 행동 1회"),
    Relic("raider_insignia", "약탈자의 문장", "전투 승리 코인 획득량 +10%"),
    Relic("merchant_scale", "상인의 저울", "상점 상품 가격 -10%"),
)

RELIC_BY_ID = {relic.relic_id: relic for relic in RELICS}
