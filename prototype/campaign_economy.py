"""Coin rewards, shop prices, and randomized shop offers."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from relics import RELIC_BY_ID, RELICS
from units import CHARACTER_DATA, PlayerCharacter


STARTING_COINS = 25
COIN_REWARDS = {"battle": 30, "elite": 55, "boss": 75}
RELIC_PRICE = 70
SHOP_REROLL_STEP = 10


@dataclass
class ShopOffer:
    category: str
    item_id: str | None
    title: str
    description: str
    price: int
    available: bool = True
    sold: bool = False
    base_price: int | None = None


def adjusted_price(base_price: int, discount: bool) -> int:
    return math.ceil(base_price * 0.9) if discount else base_price


def recruit_price(party_size: int, discount: bool = False) -> int:
    base = math.ceil(110 * math.sqrt(max(1, party_size)))
    return adjusted_price(base, discount)


def upgrade_price(level: int, discount: bool = False) -> int:
    base = math.ceil(45 * max(1, level) ** 0.25)
    return adjusted_price(base, discount)


def victory_coins(encounter_kind: str, relic_ids: list[str] | tuple[str, ...]) -> int:
    base = COIN_REWARDS[encounter_kind]
    if "raider_insignia" in relic_ids:
        return math.floor(base * 1.1 + 0.5)
    return base


def make_shop_offers(
    party: list[PlayerCharacter], relic_ids: list[str], *, rng: random.Random | None = None
) -> list[ShopOffer]:
    random_source = rng or random
    discount = "merchant_scale" in relic_ids
    party_ids = {hero.unit_id for hero in party}
    recruit_candidates = [character_id for character_id in CHARACTER_DATA if character_id not in party_ids]
    available_relics = [relic.relic_id for relic in RELICS if relic.relic_id not in relic_ids]

    if len(party) >= 4 or not recruit_candidates:
        recruit_offer = ShopOffer("recruit", None, "동료 영입", "파티 인원이 최대입니다.", 0, False)
    else:
        candidate = random_source.choice(recruit_candidates)
        base_price = recruit_price(len(party))
        recruit_offer = ShopOffer(
            "recruit",
            candidate,
            "동료 영입",
            f"{CHARACTER_DATA[candidate]['name']}을(를) 영입합니다.",
            adjusted_price(base_price, discount),
            base_price=base_price,
        )

    if party:
        hero = random_source.choice(party)
        base_price = upgrade_price(hero.level)
        upgrade_offer = ShopOffer(
            "upgrade",
            hero.unit_id,
            "캐릭터 강화",
            f"{hero.name} · 현재 Lv.{hero.level}",
            adjusted_price(base_price, discount),
            base_price=base_price,
        )
    else:
        upgrade_offer = ShopOffer("upgrade", None, "캐릭터 강화", "강화할 캐릭터가 없습니다.", 0, False)

    if available_relics:
        relic_id = random_source.choice(available_relics)
        relic = RELIC_BY_ID[relic_id]
        relic_offer = ShopOffer(
            "relic",
            relic_id,
            relic.name,
            relic.description,
            adjusted_price(RELIC_PRICE, discount),
            base_price=RELIC_PRICE,
        )
    else:
        relic_offer = ShopOffer("relic", None, "유물 구입", "새로 획득할 유물이 없습니다.", 0, False)

    return [recruit_offer, upgrade_offer, relic_offer]
