"""Launch the REDITUS ARCANUM Pico2D battle-stage prototype."""

from __future__ import annotations

import time
import random
from pathlib import Path

import pico2d as p2d

from battle import Battle
from campaign import FloorOne, FloorTwo
from campaign_economy import STARTING_COINS, ShopOffer, victory_coins
from cards import MAX_DECK_SIZE, SkillCard, enemy_skills, player_reward_card, starter_deck
from campaign_ui import CampaignScreen
from shop import ShopSession
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
        floor_map: FloorOne | FloorTwo | None = None
        map_scroll_y = 0
        map_scroll_dragging = False
        map_scroll_drag_offset = 0
        battle: Battle | None = None
        active_node_id: str | None = None
        return_to_map_at: float | None = None
        defeat_return_at: float | None = None
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
        pending_reward_target_id: str | None = None
        card_replace_cursor = -1
        coins = STARTING_COINS
        relic_ids: list[str] = []
        campaign_roster: list[PlayerCharacter] = []
        shop = ShopSession()
        pending_relic_offer: ShopOffer | None = None
        level_up_character_id: str | None = None
        level_up_stat: str | None = None
        level_up_spinning = False
        level_up_spin_started_at = 0.0
        level_up_roll_range = (1, 9)
        level_up_result: tuple[str, str, int, dict[str, int], dict[str, int]] | None = None
        last_coin_reward = 0
        reward_coins_paid = False
        running = True

        def has_reward_recipient_with_room() -> bool:
            return any(
                len(campaign_decks.get(hero.unit_id, hero.deck)) < MAX_DECK_SIZE
                for hero in campaign_roster
            )

        def abandon_card_reward() -> None:
            nonlocal battle, active_node_id, mode, map_notice, map_notice_until
            nonlocal return_to_map_at, reward_options, reward_character_id, reward_cursor
            nonlocal reward_stage, reward_character_cursor, pending_reward_card
            nonlocal pending_reward_source, pending_reward_target_id, card_replace_cursor
            if floor_map is None or active_node_id is None:
                return
            completed_node = active_node_id
            floor_map.complete_node(completed_node)
            completed_kind = floor_map.nodes[completed_node].kind
            if completed_kind == "boss":
                mode = "complete"
            else:
                mode = "map"
                map_notice = "카드 교환을 포기했습니다."
                if completed_kind != "reward" and last_coin_reward:
                    map_notice += f" · 코인 {last_coin_reward}개 획득"
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
            pending_reward_target_id = None
            card_replace_cursor = -1

        def claim_reward(character_id: str, replace_index: int | None = None) -> None:
            nonlocal battle, active_node_id, mode, map_notice, map_notice_until
            nonlocal return_to_map_at, reward_options, reward_character_id, reward_cursor
            nonlocal reward_stage, reward_character_cursor, pending_reward_card, pending_reward_source
            nonlocal pending_reward_target_id, card_replace_cursor
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
            deck = campaign_decks[character_id]
            hero = next(
                (member for member in campaign_roster if member.unit_id == character_id),
                None,
            )
            if len(deck) >= MAX_DECK_SIZE and replace_index is None:
                pending_reward_target_id = character_id
                card_replace_cursor = -1
                mode = "card_replace"
                return
            if replace_index is not None:
                if not 0 <= replace_index < len(deck):
                    return
                removed_card = deck.pop(replace_index)
                if hero:
                    for card_zone in (hero.hand, hero.discard, hero.deck):
                        if removed_card in card_zone:
                            card_zone.remove(removed_card)
                            break
            deck.append(reward_card)
            if hero:
                hero.deck.append(reward_card)
            completed_node = active_node_id
            floor_map.complete_node(completed_node)
            completed_kind = floor_map.nodes[completed_node].kind
            if completed_kind == "boss":
                mode = "complete"
            else:
                mode = "map"
                map_notice = f"{hero.name if hero else character_id}의 덱에 {reward_card.name} 추가 · {pending_reward_source}의 스킬"
                if completed_kind != "reward":
                    map_notice += f" · 코인 {last_coin_reward}개"
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
            pending_reward_target_id = None
            card_replace_cursor = -1

        def leave_shop() -> None:
            nonlocal mode, map_notice, map_notice_until, pending_relic_offer, active_node_id
            if floor_map and active_node_id:
                floor_map.complete_node(active_node_id)
            mode = "map"
            active_node_id = None
            pending_relic_offer = None
            map_notice = "상점 방문을 마쳤습니다."
            map_notice_until = time.monotonic() + 3.0

        def begin_map_reward(node_id: str) -> None:
            nonlocal mode, active_node_id, reward_options, reward_character_id
            nonlocal reward_cursor, reward_stage, reward_character_cursor
            nonlocal pending_reward_card, pending_reward_source
            nonlocal last_coin_reward
            if floor_map is None:
                return
            active_node_id = node_id
            reward_options = [
                (source_name, skill)
                for source_name, enemy_id in floor_map.reward_sources
                for skill in enemy_skills(enemy_id)
            ]
            random.shuffle(reward_options)
            reward_options = reward_options[:3]
            reward_character_id = selected_character_id
            reward_cursor = -1
            reward_stage = "card"
            reward_character_cursor = -1
            pending_reward_card = None
            pending_reward_source = None
            last_coin_reward = 0
            mode = "reward"

        def finish_level_up(roll: int) -> None:
            nonlocal mode, level_up_character_id, level_up_stat, level_up_spinning
            nonlocal level_up_roll_range, level_up_result
            hero = next(
                (member for member in campaign_roster if member.unit_id == level_up_character_id),
                None,
            )
            if hero and level_up_stat:
                before = {
                    "level": hero.level,
                    "hp": hero.hp,
                    "max_hp": hero.max_hp,
                    "attack": hero.attack,
                    "speed": hero.speed,
                }
                hero.level_up(level_up_stat, roll)
                stat_names = {"hp": "최대 체력", "attack": "공격력", "speed": "속도"}
                after = {
                    "level": hero.level,
                    "hp": hero.hp,
                    "max_hp": hero.max_hp,
                    "attack": hero.attack,
                    "speed": hero.speed,
                }
                level_up_result = (hero.name, stat_names[level_up_stat], roll, before, after)
                mode = "level_up_result"
            else:
                mode = "shop"
            level_up_character_id = None
            level_up_stat = None
            level_up_spinning = False
            level_up_roll_range = (1, 9)

        def roulette_number(now: float) -> int:
            minimum, maximum = level_up_roll_range
            return minimum + int(max(0.0, now - level_up_spin_started_at) * 13) % (maximum - minimum + 1)

        def stop_level_up(now: float) -> None:
            if level_up_spinning and level_up_stat:
                finish_level_up(roulette_number(now))

        def confirm_level_up_result() -> None:
            nonlocal level_up_result, mode
            if not level_up_result:
                return
            _, stat_name, roll, _, _ = level_up_result
            level_up_result = None
            mode = "shop"
            shop.notice = f"강화 완료 · {stat_name} +{roll}"

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
                        elif mode == "card_replace":
                            if has_reward_recipient_with_room():
                                pending_reward_target_id = None
                                mode = "reward"
                            else:
                                abandon_card_reward()
                        elif mode == "relic_replace":
                            pending_relic_offer = None
                            mode = "shop"
                            shop.notice = "유물 교체를 취소했습니다."
                        elif mode == "level_up":
                            pass
                        elif mode == "level_up_result":
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
                        map_scroll_y = 0
                        mode = "map"
                    elif mode == "battle" and battle:
                        screen.handle_key(battle, event.key)
                    elif mode == "level_up" and event.key == p2d.SDLK_SPACE:
                        stop_level_up(time.monotonic())
                    elif mode == "level_up_result" and event.key in (p2d.SDLK_RETURN, p2d.SDLK_SPACE):
                        confirm_level_up_result()
                elif event.type == p2d.SDL_KEYUP and mode == "battle" and battle:
                    screen.handle_key_up(battle, event.key)
                elif event.type == getattr(p2d, "SDL_MOUSEWHEEL", -1) and mode == "map" and floor_map:
                    wheel_y = getattr(event, "y", 0)
                    map_scroll_y = max(
                        0,
                        min(screen.max_map_scroll(floor_map), map_scroll_y + wheel_y * 120),
                    )
                elif event.type == p2d.SDL_MOUSEMOTION:
                    x = round(event.x / SCALE_X)
                    y = round((HEIGHT - event.y) / SCALE_Y)
                    if mode == "map" and floor_map and map_scroll_dragging:
                        map_scroll_y = screen.map_scroll_from_thumb_bottom(
                            y - map_scroll_drag_offset, floor_map
                        )
                    elif mode == "battle" and battle:
                        screen.handle_mouse_move(battle, x, y)
                    elif mode == "card_replace":
                        replace_index = screen.card_replace_at(x, y)
                        card_replace_cursor = replace_index if replace_index is not None else -1
                    elif mode == "reward":
                        if reward_stage == "card":
                            hover_index = screen.reward_choice_at(x, y)
                            reward_cursor = hover_index if hover_index is not None else -1
                        else:
                            hover_index = screen.reward_character_at(x, y)
                            reward_character_cursor = hover_index if hover_index is not None else -1
                elif event.type == p2d.SDL_MOUSEBUTTONUP and event.button == p2d.SDL_BUTTON_LEFT:
                    map_scroll_dragging = False
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
                        shop.reset()
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
                            map_scroll_y = 0
                            mode = "map"
                    elif mode == "map" and floor_map and selected_character_id:
                        if screen.map_scrollbar_thumb_at(x, y):
                            map_scroll_dragging = True
                            map_scroll_drag_offset = screen.map_scrollbar_drag_offset(y)
                        elif screen.map_scrollbar_track_at(x, y):
                            thumb = screen.map_scrollbar_thumb_rect
                            if thumb:
                                thumb_height = thumb[3] - thumb[1]
                                map_scroll_y = screen.map_scroll_from_thumb_bottom(
                                    y - thumb_height // 2, floor_map
                                )
                        elif screen.deck_preview_character_id:
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
                                node = floor_map.nodes.get(node_id) if node_id else None
                                if node and node.kind == "shop":
                                    active_node_id = node_id
                                    if not campaign_roster:
                                        campaign_roster = create_party([selected_character_id], campaign_decks)
                                    shop.enter(campaign_roster, relic_ids)
                                    pending_relic_offer = None
                                    mode = "shop"
                                elif node and node.kind == "reward":
                                    if not campaign_roster:
                                        campaign_roster = create_party([selected_character_id], campaign_decks)
                                    begin_map_reward(node_id)
                                elif node and node.kind in ("battle", "elite", "boss"):
                                    encounter = node.encounter_id or "corridor"
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
                                    defeat_return_at = None
                                    reward_coins_paid = False
                                    mode = "battle"
                    elif mode == "complete" and screen.floor_complete_clicked(x, y):
                        if floor_map and floor_map.floor_number == 1:
                            floor_map = FloorTwo()
                            map_scroll_y = 0
                            for hero in campaign_roster:
                                hero.hp = hero.max_hp
                                hero.alive = True
                            mode = "map"
                            map_notice = "2층 · 망각의 서고에 진입했습니다."
                            map_notice_until = time.monotonic() + 4.0
                        else:
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
                    elif mode == "card_replace" and pending_reward_target_id:
                        if screen.card_replace_cancel_clicked(x, y):
                            if has_reward_recipient_with_room():
                                pending_reward_target_id = None
                                mode = "reward"
                            else:
                                abandon_card_reward()
                        else:
                            replace_index = screen.card_replace_at(x, y)
                            if replace_index is not None:
                                claim_reward(pending_reward_target_id, replace_index)
                    elif mode == "level_up_result" and level_up_result:
                        if (
                            screen.level_up_result_confirm_clicked(x, y)
                        ):
                            confirm_level_up_result()
                    elif mode == "shop":
                        if screen.shop_leave_clicked(x, y):
                            leave_shop()
                        elif screen.shop_reroll_clicked(x, y):
                            coins = shop.reroll(coins, campaign_roster, relic_ids)
                        else:
                            offer_index = screen.shop_offer_at(x, y)
                            if offer_index is not None:
                                purchase = shop.purchase(
                                    offer_index,
                                    coins,
                                    campaign_roster,
                                    relic_ids,
                                    campaign_decks,
                                )
                                coins = purchase.coins
                                if purchase.kind == "upgrade" and purchase.item_id:
                                    level_up_character_id = purchase.item_id
                                    level_up_stat = None
                                    level_up_spinning = False
                                    level_up_roll_range = (1, 9)
                                    mode = "level_up"
                                elif purchase.kind == "replace_relic" and purchase.offer:
                                    pending_relic_offer = purchase.offer
                                    mode = "relic_replace"
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
                            shop.notice = "유물 교체를 취소했습니다."
                        else:
                            relic_index = screen.relic_replace_at(x, y)
                            if relic_index is not None and pending_relic_offer and pending_relic_offer.item_id:
                                coins = shop.replace_relic(relic_index, relic_ids, coins, pending_relic_offer)
                                if pending_relic_offer.sold:
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
                    scroll_y=map_scroll_y,
                )
            elif mode == "shop":
                screen.draw_shop(
                    coins,
                    shop.offers,
                    campaign_roster,
                    relic_ids,
                    shop.next_reroll_cost,
                    shop.notice,
                )
            elif mode == "level_up_result" and level_up_result:
                hero_name, stat_name, roll, before, after = level_up_result
                screen.draw_level_up_result(hero_name, stat_name, roll, before, after)
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
                screen.draw(battle, now, floor_map.floor_number if floor_map else 1)
                if battle.phase == "defeat":
                    if defeat_return_at is None:
                        defeat_return_at = now + 1.4
                    elif now >= defeat_return_at:
                        battle = None
                        floor_map = None
                        active_node_id = None
                        selected_character_id = None
                        campaign_roster.clear()
                        campaign_decks.clear()
                        relic_ids.clear()
                        mode = "title"
                        defeat_return_at = None
                elif battle.phase == "victory":
                    if return_to_map_at is None:
                        return_to_map_at = now + 1.1
                        if not reward_coins_paid and active_node_id:
                            encounter_kind = (
                                floor_map.nodes[active_node_id].kind
                                if floor_map and active_node_id in floor_map.nodes
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
                    screen.draw_reward_choice(
                        reward_character_id,
                        reward_options,
                        reward_cursor,
                        coins,
                        floor_map.floor_number if floor_map else 1,
                    )
                elif pending_reward_card and pending_reward_source:
                    screen.draw_reward_character_choice(
                        pending_reward_card,
                        pending_reward_source,
                        campaign_roster,
                        reward_character_cursor,
                        coins,
                        floor_map.floor_number if floor_map else 1,
                    )
            elif mode == "card_replace" and pending_reward_target_id and pending_reward_card:
                target_hero = next(
                    (hero for hero in campaign_roster if hero.unit_id == pending_reward_target_id),
                    None,
                )
                if target_hero:
                    screen.draw_card_replacement(
                        target_hero,
                        pending_reward_card,
                        pending_reward_source or "적",
                        campaign_decks.get(pending_reward_target_id, []),
                        card_replace_cursor,
                        floor_map.floor_number if floor_map else 1,
                        has_reward_recipient_with_room(),
                    )
            elif mode == "complete":
                screen.draw_floor_complete(coins, floor_map.floor_number if floor_map else 1)
            elapsed = time.monotonic() - frame_start
            if elapsed < 1 / 60:
                time.sleep(1 / 60 - elapsed)
    finally:
        p2d.close_canvas()


if __name__ == "__main__":
    main()
