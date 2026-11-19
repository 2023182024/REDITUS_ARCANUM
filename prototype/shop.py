"""Shop session state and purchase rules."""

from __future__ import annotations

from dataclasses import dataclass

from campaign_economy import SHOP_REROLL_STEP, ShopOffer, adjusted_price, make_shop_offers
from cards import SkillCard, starter_deck
from relics import MAX_RELICS, RELIC_BY_ID
from units import PlayerCharacter, create_party


@dataclass
class ShopAction:
    kind: str
    coins: int
    item_id: str | None = None
    offer: ShopOffer | None = None


class ShopSession:
    def __init__(self) -> None:
        self.offers: list[ShopOffer] = []
        self.reroll_count = 0
        self.notice = ""

    def reset(self) -> None:
        self.offers.clear()
        self.reroll_count = 0
        self.notice = ""

    @property
    def next_reroll_cost(self) -> int:
        return self.reroll_count * SHOP_REROLL_STEP

    def enter(self, party: list[PlayerCharacter], relic_ids: list[str]) -> None:
        self.offers = make_shop_offers(party, relic_ids)
        self.reroll_count = 0
        self.notice = ""

    def reroll(self, coins: int, party: list[PlayerCharacter], relic_ids: list[str]) -> int:
        cost = self.next_reroll_cost
        if coins < cost:
            self.notice = "코인이 부족합니다."
            return coins

        coins -= cost
        self.reroll_count += 1
        self.offers = make_shop_offers(party, relic_ids)
        self.notice = f"상품을 재배치했습니다. 다음 재배치 비용 {self.reroll_count * SHOP_REROLL_STEP}코인"
        return coins

    def purchase(
        self,
        offer_index: int,
        coins: int,
        party: list[PlayerCharacter],
        relic_ids: list[str],
        decks: dict[str, list[SkillCard]],
    ) -> ShopAction:
        if not 0 <= offer_index < len(self.offers):
            return ShopAction("none", coins)

        offer = self.offers[offer_index]
        if not offer.available or offer.sold or not offer.item_id:
            return ShopAction("none", coins)
        if coins < offer.price:
            self.notice = "코인이 부족합니다."
            return ShopAction("none", coins)

        if offer.category == "recruit":
            coins -= offer.price
            decks[offer.item_id] = starter_deck(offer.item_id)
            recruit = create_party([offer.item_id], decks)[0]
            party.append(recruit)
            offer.sold = True
            self.notice = f"{recruit.name}을(를) 동료로 영입했습니다."
            return ShopAction("recruit", coins, offer.item_id)

        if offer.category == "upgrade":
            coins -= offer.price
            offer.sold = True
            return ShopAction("upgrade", coins, offer.item_id)

        if offer.category == "relic":
            if len(relic_ids) >= MAX_RELICS:
                return ShopAction("replace_relic", coins, offer.item_id, offer)
            coins -= offer.price
            relic_ids.append(offer.item_id)
            offer.sold = True
            self.notice = f"{RELIC_BY_ID[offer.item_id].name}을(를) 획득했습니다."
            self.refresh_prices(relic_ids)
            return ShopAction("relic", coins, offer.item_id)

        return ShopAction("none", coins)

    def replace_relic(
        self,
        relic_index: int,
        relic_ids: list[str],
        coins: int,
        offer: ShopOffer,
    ) -> int:
        if (
            not 0 <= relic_index < len(relic_ids)
            or not offer.item_id
            or coins < offer.price
        ):
            self.notice = "코인이 부족하거나 교체 대상이 유효하지 않습니다."
            return coins

        old_relic = relic_ids[relic_index]
        new_relic = offer.item_id
        coins -= offer.price
        relic_ids[relic_index] = new_relic
        offer.sold = True
        self.refresh_prices(relic_ids)
        self.notice = (
            f"{RELIC_BY_ID[old_relic].name}을 버리고 "
            f"{RELIC_BY_ID[new_relic].name}을 획득했습니다."
        )
        return coins

    def refresh_prices(self, relic_ids: list[str]) -> None:
        discount = "merchant_scale" in relic_ids
        for offer in self.offers:
            if offer.available and not offer.sold and offer.base_price is not None:
                offer.price = adjusted_price(offer.base_price, discount)
