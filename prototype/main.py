"""Launch the REDITUS ARCANUM Pico2D battle-stage prototype."""

from __future__ import annotations

import time
import random
from pathlib import Path

import pico2d as p2d

from battle import Battle
from campaign import FloorOne
from campaign_economy import (
    SHOP_REROLL_STEP,
    STARTING_COINS,
    ShopOffer,
    adjusted_price,
    make_shop_offers,
    victory_coins,
)
from cards import SkillCard, player_reward_card, starter_deck
from campaign_ui import CampaignScreen
from relics import MAX_RELICS, RELIC_BY_ID
from units import CHARACTER_DATA, PlayerCharacter, create_party
from ui import HEIGHT, SCALE_X, SCALE_Y, WIDTH


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    # Use SDL's best available texture scaling filter for downscaled images.
    p2d.SDL_SetHint(p2d.SDL_HINT_RENDER_SCALE_QUALITY, b"2")
    p2d.open_canvas(WIDTH, HEIGHT)
    try:
        core = p2d.pico2d
        if getattr(core, "window", None) and getattr(core, "SDL_SetWindowTitle", None):
            core.SDL_SetWindowTitle(core.window, "REDITUS ARCANUM · BATTLE".encode("utf-8"))
        screen = CampaignScreen(project_root)
        mode = "title"
        offers: list[str] = []
        selected_character_id: str | None = None
        floor_map: FloorOne | None = None
        battle: Battle | None = None
        active_node_id: str | None = None
        return_to_map_at: float | None = None
        map_notice = ""
        map_notice_until = 0.0
        campaign_decks: dict[str, list[SkillCard]] = {}
        reward_options: list[tuple[str, SkillCard]] = []
        reward_character_id: str | None = None
        reward_cursor = -1
        reward_stage = "card"
        reward_character_cursor = -1
        pending_reward_card: SkillCard | None = None
        pending_reward_source: str | None = None
        coins = STARTING_COINS
        relic_ids: list[str] = []
        campaign_roster: list[PlayerCharacter] = []
        shop_offers: list[ShopOffer] = []
        shop_reroll_count = 0
        shop_notice = ""
        pending_relic_offer: ShopOffer | None = None
        level_up_character_id: str | None = None
        level_up_stat: str | None = None
        level_up_spinning = False
        level_up_spin_started_at = 0.0
        level_up_roll_range = (1, 9)
        last_coin_reward = 0
        reward_coins_paid = False
        running = True

        def claim_reward(character_id: str) -> None:
            nonlocal battle, active_node_id, mode, map_notice, map_notice_until
            nonlocal return_to_map_at, reward_options, reward_character_id, reward_cursor
            nonlocal reward_stage, reward_character_cursor, pending_reward_card, pending_reward_source
            nonlocal campaign_roster
            if (
                not any(member.unit_id == character_id for member in campaign_roster)
                or pending_reward_card is None
                or pending_reward_source is None
                or active_node_id is None
                or floor_map is None
            ):
                return
            reward_card = pending_reward_card
            if character_id not in campaign_decks:
                campaign_decks[character_id] = starter_deck(character_id)
            campaign_decks[character_id].append(reward_card)
            hero = next(
                (member for member in campaign_roster if member.unit_id == character_id),
                None,
            )
            if hero:
                hero.deck.append(reward_card)
            completed_node = active_node_id
            floor_map.complete_node(completed_node)
            if completed_node == "boss":
                mode = "complete"
            else:
                mode = "map"
                map_notice = (
                    f"{hero.name if hero else character_id}의 덱에 {reward_card.name} 추가 · "
                    f"{pending_reward_source}의 스킬, 코인 {last_coin_reward}개"
                )
                map_notice_until = time.monotonic() + 4.0
            battle = None
            active_node_id = None
            return_to_map_at = None
            reward_options = []
            reward_character_id = None
            reward_cursor = -1
            reward_stage = "card"
            reward_character_cursor = -1
            pending_reward_card = None
            pending_reward_source = None

        def leave_shop() -> None:
            nonlocal mode, map_notice, map_notice_until, pending_relic_offer
            if floor_map:
                floor_map.complete_node("shop")
            mode = "map"
            pending_relic_offer = None
            map_notice = "상점 방문을 마쳤습니다."
            map_notice_until = time.monotonic() + 3.0

        def refresh_shop_prices() -> None:
            discount = "merchant_scale" in relic_ids
            for offer in shop_offers:
                if offer.available and not offer.sold and offer.base_price is not None:
                    offer.price = adjusted_price(offer.base_price, discount)

        def finish_level_up(roll: int) -> None:
            nonlocal mode, level_up_character_id, level_up_stat, level_up_spinning
            nonlocal shop_notice, level_up_roll_range
            hero = next(
                (member for member in campaign_roster if member.unit_id == level_up_character_id),
                None,
            )
            if hero and level_up_stat:
                hero.level_up(level_up_stat, roll)
                stat_names = {"hp": "최대 체력", "attack": "공격력", "speed": "속도"}
                shop_notice = f"{hero.name} Lv.{hero.level} · {stat_names[level_up_stat]} +{roll}"
            level_up_character_id = None
            level_up_stat = None
            level_up_spinning = False
            level_up_roll_range = (1, 9)
            mode = "shop"

        def roulette_number(now: float) -> int:
            minimum, maximum = level_up_roll_range
            return minimum + int(max(0.0, now - level_up_spin_started_at) * 13) % (maximum - minimum + 1)

        def stop_level_up(now: float) -> None:
            if level_up_spinning and level_up_stat:
                finish_level_up(roulette_number(now))

        while running:
            frame_start = time.monotonic()
            for event in p2d.get_events():
                if event.type == p2d.SDL_QUIT:
                    running = False
                elif event.type == p2d.SDL_KEYDOWN:
                    if event.key == p2d.SDLK_ESCAPE:
                        if mode == "reward":
                            pass
                        elif mode == "battle" and battle:
                            screen.handle_key(battle, event.key)
                        elif mode == "shop":
                            leave_shop()
                        elif mode == "relic_replace":
                            pending_relic_offer = None
                            mode = "shop"
                            shop_notice = "유물 교체를 취소했습니다."
                        elif mode == "level_up":
                            pass
                        elif mode in ("select", "map", "complete"):
                            if mode == "map" and screen.deck_preview_character_id:
                                screen.close_deck_preview()
                            else:
                                mode = "title"
                                selected_character_id = None
                        else:
                            running = False
                    elif mode == "select" and event.key == p2d.SDLK_RETURN and selected_character_id:
                        floor_map = FloorOne()
                        mode = "map"
                    elif mode == "battle" and battle:
                        screen.handle_key(battle, event.key)
                    elif mode == "level_up" and event.key == p2d.SDLK_SPACE:
                        stop_level_up(time.monotonic())
                elif event.type == p2d.SDL_KEYUP and mode == "battle" and battle:
                    screen.handle_key_up(battle, event.key)
                elif event.type == p2d.SDL_MOUSEMOTION:
                    x = round(event.x / SCALE_X)
                    y = round((HEIGHT - event.y) / SCALE_Y)
                    if mode == "battle" and battle:
                        screen.handle_mouse_move(battle, x, y)
                    elif mode == "reward":
                        if reward_stage == "card":
                            hover_index = screen.reward_choice_at(x, y)
                            reward_cursor = hover_index if hover_index is not None else -1
                        else:
                            hover_index = screen.reward_character_at(x, y)
                            reward_character_cursor = hover_index if hover_index is not None else -1
                elif event.type == p2d.SDL_MOUSEBUTTONDOWN and event.button == p2d.SDL_BUTTON_LEFT:
                    x = round(event.x / SCALE_X)
                    y = round((HEIGHT - event.y) / SCALE_Y)
                    if mode == "title" and screen.title_start_clicked(x, y):
                        offers = random.sample(list(CHARACTER_DATA), 2)
                        selected_character_id = None
                        campaign_decks.clear()
                        campaign_roster.clear()
                        relic_ids.clear()
                        coins = STARTING_COINS
                        shop_offers = []
                        shop_reroll_count = 0
                        reward_coins_paid = False
                        mode = "select"
                    elif mode == "select":
                        clicked_character = screen.selected_character_at(x, y)
                        if clicked_character:
                            selected_character_id = clicked_character
                            campaign_decks.clear()
                            campaign_decks[clicked_character] = starter_deck(clicked_character)
                            campaign_roster.clear()
                        elif screen.confirm_selection_clicked(x, y) and selected_character_id:
                            floor_map = FloorOne()
                            mode = "map"
                    elif mode == "map" and floor_map and selected_character_id:
                        if screen.deck_preview_character_id:
                            if screen.map_deck_preview_close_clicked(x, y):
                                screen.close_deck_preview()
                            else:
                                clicked_character = screen.map_character_at(x, y)
                                if clicked_character:
                                    screen.toggle_deck_preview(clicked_character)
                                else:
                                    screen.close_deck_preview()
                        elif screen.map_restart_clicked(x, y):
                            mode = "title"
                            selected_character_id = None
                        else:
                            clicked_character = screen.map_character_at(x, y)
                            if clicked_character:
                                screen.toggle_deck_preview(clicked_character)
                            else:
                                node_id = screen.map_node_at(x, y, floor_map)
                                if node_id == "shop":
                                    if not campaign_roster:
                                        campaign_roster = create_party([selected_character_id], campaign_decks)
                                    shop_offers = make_shop_offers(campaign_roster, relic_ids)
                                    shop_reroll_count = 0
                                    shop_notice = ""
                                    pending_relic_offer = None
                                    mode = "shop"
                                elif node_id and node_id in ("battle_1", "battle_2", "elite", "boss"):
                                    encounter = {
                                        "elite": "floor1_elite",
                                        "boss": "floor1_boss",
                                    }.get(node_id, "corridor")
                                    if campaign_roster:
                                        battle = Battle(
                                            encounter_id=encounter,
                                            decks=campaign_decks,
                                            relic_ids=relic_ids,
                                            roster=campaign_roster,
                                        )
                                    else:
                                        battle = Battle(
                                            [selected_character_id],
                                            encounter,
                                            decks=campaign_decks,
                                            relic_ids=relic_ids,
                                        )
                                        campaign_roster = battle.party
                                    active_node_id = node_id
                                    return_to_map_at = None
                                    reward_coins_paid = False
                                    mode = "battle"
                    elif mode == "complete" and screen.floor_complete_clicked(x, y):
                        mode = "title"
                        selected_character_id = None
                    elif mode == "battle" and battle:
                        screen.handle_mouse_click(battle, x, y)
                    elif mode == "reward" and reward_options:
                        if reward_stage == "card":
                            choice_index = screen.reward_choice_at(x, y)
                            if choice_index is not None:
                                reward_cursor = choice_index
                                source_name, enemy_skill = reward_options[choice_index]
                                pending_reward_card = player_reward_card(enemy_skill)
                                pending_reward_source = source_name
                                reward_stage = "character"
                                reward_character_cursor = -1
                        else:
                            character_index = screen.reward_character_at(x, y)
                            if character_index is not None and character_index < len(campaign_roster):
                                reward_character_cursor = character_index
                                claim_reward(campaign_roster[character_index].unit_id)
                    elif mode == "shop":
                        if screen.shop_leave_clicked(x, y):
                            leave_shop()
                        elif screen.shop_reroll_clicked(x, y):
                            reroll_cost = shop_reroll_count * SHOP_REROLL_STEP
                            if coins >= reroll_cost:
                                coins -= reroll_cost
                                shop_reroll_count += 1
                                shop_offers = make_shop_offers(campaign_roster, relic_ids)
                                shop_notice = f"상품을 재배치했습니다. 다음 재배치 비용 {shop_reroll_count * SHOP_REROLL_STEP}코인"
                            else:
                                shop_notice = "코인이 부족합니다."
                        else:
                            offer_index = screen.shop_offer_at(x, y)
                            if offer_index is not None:
                                offer = shop_offers[offer_index]
                                if offer.available and not offer.sold:
                                    if coins < offer.price:
                                        shop_notice = "코인이 부족합니다."
                                    elif offer.category == "recruit" and offer.item_id:
                                        coins -= offer.price
                                        campaign_decks[offer.item_id] = starter_deck(offer.item_id)
                                        recruit = create_party([offer.item_id], campaign_decks)[0]
                                        campaign_roster.append(recruit)
                                        offer.sold = True
                                        shop_notice = f"{recruit.name}을(를) 동료로 영입했습니다."
                                    elif offer.category == "upgrade" and offer.item_id:
                                        coins -= offer.price
                                        offer.sold = True
                                        level_up_character_id = offer.item_id
                                        level_up_stat = None
                                        level_up_spinning = False
                                        level_up_roll_range = (1, 9)
                                        mode = "level_up"
                                    elif offer.category == "relic" and offer.item_id:
                                        if len(relic_ids) >= MAX_RELICS:
                                            pending_relic_offer = offer
                                            mode = "relic_replace"
                                        else:
                                            coins -= offer.price
                                            relic_ids.append(offer.item_id)
                                            offer.sold = True
                                            shop_notice = f"{RELIC_BY_ID[offer.item_id].name}을(를) 획득했습니다."
                                            refresh_shop_prices()
                    elif mode == "level_up":
                        selected_stat = screen.level_up_stat_at(x, y)
                        if selected_stat:
                            level_up_stat = selected_stat
                            hero = next(
                                (member for member in campaign_roster if member.unit_id == level_up_character_id),
                                None,
                            )
                            if hero:
                                level_up_roll_range = hero.level_up_roll_range(selected_stat)
                        elif screen.level_up_spin_clicked(x, y) and level_up_stat:
                            if level_up_spinning:
                                stop_level_up(time.monotonic())
                            else:
                                level_up_spinning = True
                                level_up_spin_started_at = time.monotonic()
                    elif mode == "relic_replace":
                        if screen.relic_replace_cancel_clicked(x, y):
                            pending_relic_offer = None
                            mode = "shop"
                            shop_notice = "유물 교체를 취소했습니다."
                        else:
                            relic_index = screen.relic_replace_at(x, y)
                            if relic_index is not None and pending_relic_offer and pending_relic_offer.item_id:
                                if coins >= pending_relic_offer.price:
                                    old_relic = relic_ids[relic_index]
                                    new_relic = pending_relic_offer.item_id
                                    coins -= pending_relic_offer.price
                                    relic_ids[relic_index] = new_relic
                                    pending_relic_offer.sold = True
                                    refresh_shop_prices()
                                    shop_notice = (
                                        f"{RELIC_BY_ID[old_relic].name}을 버리고 "
                                        f"{RELIC_BY_ID[new_relic].name}을 획득했습니다."
                                    )
                                    pending_relic_offer = None
                                    mode = "shop"
            now = time.monotonic()
            if mode == "title":
                screen.draw_title()
            elif mode == "select":
                screen.draw_character_select(offers, selected_character_id)
            elif mode == "map" and floor_map and selected_character_id:
                screen.draw_map(
                    floor_map,
                    selected_character_id,
                    map_notice if now < map_notice_until else "",
                    campaign_decks,
                    coins=coins,
                    party=campaign_roster,
                    relic_ids=relic_ids,
                )
            elif mode == "shop":
                screen.draw_shop(
                    coins,
                    shop_offers,
                    campaign_roster,
                    relic_ids,
                    shop_reroll_count * SHOP_REROLL_STEP,
                    shop_notice,
                )
            elif mode == "level_up" and level_up_character_id:
                hero = next(
                    (member for member in campaign_roster if member.unit_id == level_up_character_id),
                    None,
                )
                if hero:
                    display_roll = roulette_number(now) if level_up_spinning else 0
                    screen.draw_level_up(
                        hero,
                        level_up_stat,
                        level_up_spinning,
                        display_roll,
                        level_up_roll_range,
                        coins,
                    )
            elif mode == "relic_replace" and pending_relic_offer and pending_relic_offer.item_id:
                screen.draw_relic_replacement(
                    relic_ids,
                    pending_relic_offer.item_id,
                    coins,
                    pending_relic_offer.price,
                )
            elif mode == "battle" and battle:
                battle.update(now)
                screen.draw(battle, now)
                if battle.phase == "victory":
                    if return_to_map_at is None:
                        return_to_map_at = now + 1.1
                        if not reward_coins_paid and active_node_id:
                            encounter_kind = (
                                "boss" if active_node_id == "boss"
                                else "elite" if active_node_id == "elite"
                                else "battle"
                            )
                            last_coin_reward = victory_coins(encounter_kind, relic_ids)
                            coins += last_coin_reward
                            reward_coins_paid = True
                    elif now >= return_to_map_at:
                        reward_character_id = selected_character_id
                        reward_options = [
                            (enemy.name, skill)
                            for enemy in battle.enemies
                            if not enemy.alive
                            for skill in enemy.skills
                        ]
                        reward_cursor = -1
                        reward_stage = "card"
                        reward_character_cursor = -1
                        pending_reward_card = None
                        pending_reward_source = None
                        mode = "reward"
                        return_to_map_at = None
            elif mode == "reward" and reward_character_id:
                if reward_stage == "card":
                    screen.draw_reward_choice(reward_character_id, reward_options, reward_cursor, coins)
                elif pending_reward_card and pending_reward_source:
                    screen.draw_reward_character_choice(
                        pending_reward_card,
                        pending_reward_source,
                        campaign_roster,
                        reward_character_cursor,
                        coins,
                    )
            elif mode == "complete":
                screen.draw_floor_complete(coins)
            elapsed = time.monotonic() - frame_start
            if elapsed < 1 / 60:
                time.sleep(1 / 60 - elapsed)
    finally:
        p2d.close_canvas()


if __name__ == "__main__":
    main()
