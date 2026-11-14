"""Launch the REDITUS ARCANUM Pico2D battle-stage prototype."""

from __future__ import annotations

import time
import random
from pathlib import Path

import pico2d as p2d

from battle import Battle
from campaign import FloorOne
from cards import SkillCard, player_reward_card, starter_deck
from campaign_ui import CampaignScreen
from units import CHARACTER_DATA
from ui import HEIGHT, SCALE_X, SCALE_Y, WIDTH


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    p2d.open_canvas(WIDTH, HEIGHT)
    p2d.SDL_SetHint(p2d.SDL_HINT_RENDER_SCALE_QUALITY, b"1")
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
        reward_cursor = 0
        running = True

        def claim_reward(index: int) -> None:
            nonlocal battle, active_node_id, mode, map_notice, map_notice_until
            nonlocal return_to_map_at, reward_options, reward_character_id, reward_cursor
            if (
                index < 0
                or index >= len(reward_options)
                or selected_character_id is None
                or active_node_id is None
                or floor_map is None
            ):
                return
            source_name, enemy_skill = reward_options[index]
            reward_card = player_reward_card(enemy_skill)
            if selected_character_id not in campaign_decks:
                campaign_decks[selected_character_id] = starter_deck(selected_character_id)
            campaign_decks[selected_character_id].append(reward_card)
            completed_node = active_node_id
            floor_map.complete_node(completed_node)
            if completed_node == "boss":
                mode = "complete"
            else:
                mode = "map"
                map_notice = f"{reward_card.name} · {source_name}의 스킬을 덱에 추가했습니다."
                map_notice_until = time.monotonic() + 4.0
            battle = None
            active_node_id = None
            return_to_map_at = None
            reward_options = []
            reward_character_id = None
            reward_cursor = 0

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
                    elif mode == "reward" and reward_options:
                        if event.key in (p2d.SDLK_LEFT, p2d.SDLK_UP):
                            reward_cursor = (reward_cursor - 1) % len(reward_options)
                        elif event.key in (p2d.SDLK_RIGHT, p2d.SDLK_DOWN):
                            reward_cursor = (reward_cursor + 1) % len(reward_options)
                        elif event.key in (p2d.SDLK_SPACE, p2d.SDLK_RETURN):
                            claim_reward(reward_cursor)
                elif event.type == p2d.SDL_MOUSEMOTION and mode == "battle" and battle:
                    x = round(event.x / SCALE_X)
                    y = round((HEIGHT - event.y) / SCALE_Y)
                    screen.handle_mouse_move(battle, x, y)
                elif event.type == p2d.SDL_MOUSEBUTTONDOWN and event.button == p2d.SDL_BUTTON_LEFT:
                    x = round(event.x / SCALE_X)
                    y = round((HEIGHT - event.y) / SCALE_Y)
                    if mode == "title" and screen.title_start_clicked(x, y):
                        offers = random.sample(list(CHARACTER_DATA), 2)
                        selected_character_id = None
                        mode = "select"
                    elif mode == "select":
                        clicked_character = screen.selected_character_at(x, y)
                        if clicked_character:
                            selected_character_id = clicked_character
                            campaign_decks.clear()
                            campaign_decks[clicked_character] = starter_deck(clicked_character)
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
                                    floor_map.complete_node(node_id)
                                    map_notice = "상점 콘텐츠는 미구현이라 구매 없이 다음 경로로 이동합니다."
                                    map_notice_until = time.monotonic() + 3.0
                                elif node_id and node_id in ("battle_1", "battle_2", "boss"):
                                    encounter = "floor1_boss" if node_id == "boss" else "corridor"
                                    battle = Battle([selected_character_id], encounter, decks=campaign_decks)
                                    active_node_id = node_id
                                    return_to_map_at = None
                                    mode = "battle"
                    elif mode == "complete" and screen.floor_complete_clicked(x, y):
                        mode = "title"
                        selected_character_id = None
                    elif mode == "battle" and battle:
                        screen.handle_mouse_click(battle, x, y)
                    elif mode == "reward" and reward_options:
                        choice_index = screen.reward_choice_at(x, y)
                        if choice_index is not None:
                            reward_cursor = choice_index
                            claim_reward(choice_index)
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
                    campaign_decks.get(selected_character_id),
                )
            elif mode == "battle" and battle:
                battle.update(now)
                screen.draw(battle, now)
                if battle.phase == "victory":
                    if return_to_map_at is None:
                        return_to_map_at = now + 1.1
                    elif now >= return_to_map_at:
                        reward_character_id = selected_character_id
                        reward_options = [
                            (enemy.name, skill)
                            for enemy in battle.enemies
                            if not enemy.alive
                            for skill in enemy.skills
                        ]
                        reward_cursor = 0
                        mode = "reward"
                        return_to_map_at = None
            elif mode == "reward" and reward_character_id:
                screen.draw_reward_choice(reward_character_id, reward_options, reward_cursor)
            elif mode == "complete":
                screen.draw_floor_complete()
            elapsed = time.monotonic() - frame_start
            if elapsed < 1 / 60:
                time.sleep(1 / 60 - elapsed)
    finally:
        p2d.close_canvas()


if __name__ == "__main__":
    main()
