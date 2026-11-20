"""Campaign screens and the scrollable expedition map."""

from __future__ import annotations

import textwrap
from dataclasses import dataclass

from campaign import FloorOne, FloorTwo, MapNode
from campaign_economy import ShopOffer
from cards import MAX_DECK_SIZE, PLAYER_CARD_DAMAGE_SCALE, SkillCard, starter_deck
from relics import MAX_RELICS, RELIC_BY_ID
from units import PlayerCharacter, character_info
from ui import (
    BattleScreen, BLUE, CARD_W, CORAL, DESIGN_HEIGHT, DESIGN_WIDTH, GOLD, HEIGHT,
    INK, LINE, MINT, MUTED, PANEL, PANEL_LIGHT, SCALE_X, SCALE_Y, TEXT, WIDTH,
)

import pico2d as p2d


# Cell order in the three-column atlas, read from the top left.
MAP_SEALS = {
    "start": (0, "시작"), "battle": (1, "전투"), "elite": (2, "정예"),
    "shop": (3, "상점"), "reward": (4, "보상"), "boss": (5, "층 보스"),
}
SEPIA = (66, 42, 27)
BRASS = (166, 121, 57)
LEATHER = (62, 35, 32)
MAP_NODE_HALF_HEIGHT = 58


@dataclass
class MapPan:
    start_x: int
    start_y: int
    pressed_node: str | None
    last_drag_y: int | None = None

    def move(self, x: int, y: int, scroll_y: int, maximum: int) -> int:
        previous_y = self.last_drag_y
        if previous_y is None:
            # Allow small movements while clicking a node.
            if max(abs(x - self.start_x), abs(y - self.start_y)) < 8:
                return scroll_y
            previous_y = self.start_y
        self.last_drag_y = y
        return max(0, min(maximum, scroll_y + previous_y - y))


class CampaignScreen(BattleScreen):
    def __init__(self, asset_root):
        super().__init__(asset_root)
        self.start_screen_image = p2d.load_image(str(asset_root / "images" / "start_screen.png"))
        map_art = asset_root / "images" / "ui" / "stage_map"
        self.map_scroll = p2d.load_image(str(map_art / "scroll.png"))
        self.map_seals = p2d.load_image(str(map_art / "seals.png"))
        self.map_binding = p2d.load_image(str(map_art / "binding.png"))
        self.map_nameplate = p2d.load_image(str(map_art / "nameplate.png"))
        self.start_rect = (535, 230, 905, 325)
        self.confirm_rect = (540, 125, 900, 205)
        self.character_rects: dict[str, tuple[int, int, int, int]] = {}
        self.map_character_rects: dict[str, tuple[int, int, int, int]] = {}
        self.map_node_rects: dict[str, tuple[int, int, int, int]] = {}
        self.map_viewport = (330, 80, 1410, 844)
        self.map_scrollbar_track_rect = (1380, 80, 1398, 830)
        self.map_scrollbar_thumb_rect: tuple[int, int, int, int] | None = None
        self.deck_preview_character_id: str | None = None
        self.deck_preview_close_rect = (1315, 738, 1380, 784)
        self.reward_choice_rects: list[tuple[int, int, int, int]] = []
        self.reward_character_rects: list[tuple[int, int, int, int]] = []
        self.card_replace_rects: list[tuple[int, int, int, int]] = []
        self.card_replace_cancel_rect = (74, 115, 310, 170)
        self.shop_offer_rects: list[tuple[int, int, int, int]] = []
        self.shop_reroll_rect = (860, 112, 1090, 184)
        self.shop_leave_rect = (1120, 112, 1350, 184)
        self.level_up_stat_rects: dict[str, tuple[int, int, int, int]] = {}
        self.level_up_spin_rect = (560, 250, 880, 330)
        self.level_up_result_confirm_rect = (460, 145, 980, 245)
        self.relic_replace_rects: list[tuple[int, int, int, int]] = []
        self.relic_replace_cancel_rect = (580, 155, 860, 220)
        self.map_restart_rect = (50, 868, 202, 910)
        self.complete_rect = (540, 245, 900, 330)

    def _clear_page(self) -> None:
        p2d.clear_canvas()
        self.rect(0, 0, DESIGN_WIDTH, DESIGN_HEIGHT, INK)

    def draw_title(self) -> None:
        self._clear_page()
        self.start_screen_image.draw(WIDTH // 2, HEIGHT // 2, WIDTH, HEIGHT)
        self.text(720, 830, "REDITUS ARCANUM", 38, (0, 0, 0), centered=True)
        self.panel(*self.start_rect[:2], self.start_rect[2] - self.start_rect[0], self.start_rect[3] - self.start_rect[1], (52, 48, 42), GOLD)
        self.text(720, 278, "게임 시작", 26, GOLD, centered=True)
        p2d.update_canvas()

    def draw_character_select(self, offers: list[str], selected_id: str | None) -> None:
        self._clear_page()
        self.character_rects.clear()
        self.text(720, 900, "동행자 선택", 30, TEXT, centered=True)
        self.text(720, 858, "제시된 두 명 중 한 명을 선택하세요", 15, MUTED, centered=True)
        centers = (505, 935)
        for character_id, center_x in zip(offers, centers):
            data = character_info(character_id)
            rect = (center_x - 180, 265, center_x + 180, 805)
            self.character_rects[character_id] = rect
            selected = character_id == selected_id
            border = GOLD if selected else LINE
            fill = (39, 40, 48) if selected else PANEL
            self.panel(rect[0], rect[1], rect[2] - rect[0], rect[3] - rect[1], fill, border)
            self.text(center_x, 765, data["name"], 21, data["accent"], centered=True)
            self.circle(center_x, 580, 143, (34, 40, 54), filled=True)
            self.image(self.portraits[character_id], center_x, 585, 166, 249)
            self.text(center_x, 423, f"HP {data['hp']}   ·   ATK {data['attack']}   ·   SPD {data['speed']}", 14, TEXT, centered=True)
            self.text(center_x, 382, data["trait"], 14, MUTED, centered=True)
            self.text(center_x, 318, "선택됨" if selected else "클릭하여 선택", 14, GOLD if selected else MUTED, centered=True)
        button_fill = (52, 48, 42) if selected_id else PANEL_LIGHT
        button_edge = GOLD if selected_id else LINE
        self.panel(self.confirm_rect[0], self.confirm_rect[1], self.confirm_rect[2] - self.confirm_rect[0], self.confirm_rect[3] - self.confirm_rect[1], button_fill, button_edge)
        self.text(720, 165, "1층 맵으로", 19, GOLD if selected_id else MUTED, centered=True)
        p2d.update_canvas()

    def draw_map(
        self,
        floor_map: FloorOne | FloorTwo,
        character_id: str,
        notice: str = "",
        decks: dict[str, list[SkillCard]] | None = None,
        coins: int = 0,
        party: list[PlayerCharacter] | None = None,
        relic_ids: list[str] | None = None,
        scroll_y: int = 0,
    ) -> None:
        p2d.clear_canvas()
        self.rect(0, 0, DESIGN_WIDTH, DESIGN_HEIGHT, (35, 26, 24))
        self.map_node_rects.clear()
        self.map_character_rects.clear()
        self.text(875, 919, floor_map.floor_title, 30, GOLD, centered=True)
        self.text(353, 925, f"코인 {coins}", 17, GOLD)
        if relic_ids:
            relic_names = " · ".join(RELIC_BY_ID[relic_id].name for relic_id in relic_ids[:5])
            self.text(353, 900, f"유물: {relic_names}", 12, MINT)
        self.panel(self.map_restart_rect[0], self.map_restart_rect[1], self.map_restart_rect[2] - self.map_restart_rect[0], self.map_restart_rect[3] - self.map_restart_rect[1], LEATHER, BRASS)
        self.text((self.map_restart_rect[0] + self.map_restart_rect[2]) / 2, 889, "처음으로", 13, MUTED, centered=True)

        self._draw_route_panel(character_id, party, floor_map.floor_number)
        maximum = self.max_map_scroll(floor_map)
        scroll_y = max(0, min(scroll_y, maximum))
        self._draw_scroll_paper(scroll_y, maximum)
        left, bottom, right, top = self.map_viewport
        clip = p2d.SDL_Rect(round(left * SCALE_X), HEIGHT - round(top * SCALE_Y),
                            round((right - left) * SCALE_X), round((top - bottom) * SCALE_Y))
        renderer = p2d.pico2d.renderer
        p2d.SDL_RenderSetClipRect(renderer, clip)
        try:
            for source_id, target_id in floor_map.edges:
                source, target = floor_map.nodes[source_id], floor_map.nodes[target_id]
                color = SEPIA if source.cleared or target.unlocked else (134, 105, 76)
                self.line(source.x, source.y - scroll_y, target.x, target.y - scroll_y, color)
            for node in floor_map.nodes.values():
                self._draw_map_node(node, scroll_y)
        finally:
            p2d.SDL_RenderSetClipRect(renderer, None)
        self._draw_map_scrollbar(floor_map, scroll_y)

        hint = "휠 또는 왼쪽 버튼 드래그로 지도 이동 · 진행 가능한 노드를 선택하세요" if maximum else "진행 가능한 노드를 선택하세요"
        self.text(875, 20, notice[:62] or hint, 14, GOLD if notice else (211, 191, 163), centered=True)
        if self.deck_preview_character_id:
            self._draw_deck_preview(
                self.deck_preview_character_id,
                decks.get(self.deck_preview_character_id) if decks else None,
            )
        p2d.update_canvas()

    def _draw_route_panel(
        self,
        character_id: str,
        party: list[PlayerCharacter] | None = None,
        floor_number: int = 1,
    ) -> None:
        self.image_stretched(self.map_binding, 20, 44, 308, 807)
        party = party or []
        party_ids = [hero.unit_id for hero in party] if party else [character_id]
        self.text(177, 808, f"동행자  {len(party_ids)} / 4", 22, GOLD, centered=True)
        slot_rects = ((48, 618, 306, 780), (48, 448, 306, 610), (48, 278, 306, 440), (48, 108, 306, 270))
        for index, rect in enumerate(slot_rects):
            member_id = party_ids[index] if index < len(party_ids) else None
            if member_id:
                hero = party[index] if party else None
                data = character_info(member_id)
                self.map_character_rects[member_id] = rect
                self.panel(rect[0], rect[1], rect[2] - rect[0], rect[3] - rect[1], LEATHER, BRASS)
                self.image(self.portraits[member_id], rect[0] + 64, rect[1] + 81, 108, 162)
                info_x = rect[0] + 155
                name = (hero.name if hero else data["name"]).split(" · ", 1)[0]
                hp_text = f"HP {hero.hp}/{hero.max_hp}" if hero else f"HP {data['hp']}"
                attack = hero.attack if hero else data["attack"]
                speed = hero.speed if hero else data["speed"]
                level = hero.level if hero else 1
                self.text(info_x, rect[1] + 137, f"{name} · Lv.{level}", 14, data["accent"])
                self.text(info_x, rect[1] + 111, hp_text, 12, TEXT)
                self._bar(info_x, rect[1] + 93, 82, 5, hero.hp / hero.max_hp if hero else 1.0, (180, 91, 72))
                self.text(info_x, rect[1] + 76, f"ATK {attack} · SPD {speed}", 12, (216, 193, 166))
                self.text(info_x, rect[1] + 20, "클릭하여 덱 보기", 9, GOLD)
            else:
                self.rect(rect[0], rect[1], rect[2] - rect[0], rect[3] - rect[1], BRASS, filled=False)
                self.text(rect[0] + 64, rect[1] + 81, "◇", 24, BRASS, centered=True)
                self.text(rect[0] + 158, rect[1] + 95, "영입 대기 슬롯", 11, MUTED)
        self.text(58, 87, f"층 진행  {floor_number} / 2", 13, GOLD)

    def _draw_scroll_paper(self, scroll_y: int, maximum: int) -> None:
        left, bottom, right, top = self.map_viewport
        x = round((left + right) / 2 * SCALE_X)
        width = round((right - left - 24) * SCALE_X)
        height = top - bottom
        # Bottom-origin source rows for the exposed paper between the two rolls.
        body_start, body_end = 128, 1396
        texture_height = min(body_end - body_start, height + maximum)
        ratio = texture_height / (height + maximum)
        low = body_start + round(scroll_y * ratio)
        high = body_start + round((scroll_y + height) * ratio)
        for src_y, src_h, dst_y, dst_h in (
            (low, high - low, bottom, height),
            (58, body_start - 58, bottom - 42, 42),
            (body_end, 1474 - body_end, top, 42),
        ):
            self.map_scroll.clip_draw(
                0, src_y, self.map_scroll.w, src_h, x,
                round((dst_y + dst_h / 2) * SCALE_Y), width, round(dst_h * SCALE_Y),
            )

    def max_map_scroll(self, floor_map: FloorOne | FloorTwo) -> int:
        if floor_map.floor_number < 2:
            return 0
        highest_node = max(node.y for node in floor_map.nodes.values()) + MAP_NODE_HALF_HEIGHT
        return max(0, highest_node - self.map_viewport[3])

    def _draw_map_scrollbar(self, floor_map: FloorOne | FloorTwo, scroll_y: int) -> None:
        self.map_scrollbar_thumb_rect = None
        maximum = self.max_map_scroll(floor_map)
        if maximum <= 0:
            return
        x0, y0, x1, y1 = self.map_scrollbar_track_rect
        track_height = y1 - y0
        content_height = self.map_viewport[3] - self.map_viewport[1] + maximum
        thumb_height = max(64, round(track_height * track_height / content_height))
        thumb_height = min(track_height, thumb_height)
        thumb_range = track_height - thumb_height
        thumb_bottom = y0 + round(thumb_range * scroll_y / maximum)
        self.panel(x0, y0, x1 - x0, track_height, LEATHER, BRASS)
        self.map_scrollbar_thumb_rect = (x0, thumb_bottom, x1, thumb_bottom + thumb_height)
        self.panel(x0 + 2, thumb_bottom, x1 - x0 - 4, thumb_height, BRASS, GOLD)

    def can_pan_map_at(self, x: int, y: int, floor_map: FloorOne | FloorTwo) -> bool:
        return self._inside(x, y, self.map_viewport) and self.max_map_scroll(floor_map) > 0

    def map_scrollbar_thumb_at(self, x: int, y: int) -> bool:
        return self.map_scrollbar_thumb_rect is not None and self._inside(x, y, self.map_scrollbar_thumb_rect)

    def map_scrollbar_track_at(self, x: int, y: int) -> bool:
        return self.map_scrollbar_thumb_rect is not None and self._inside(x, y, self.map_scrollbar_track_rect)

    def map_scrollbar_drag_offset(self, y: int) -> int:
        if self.map_scrollbar_thumb_rect is None:
            return 0
        return y - self.map_scrollbar_thumb_rect[1]

    def map_scroll_from_thumb_bottom(self, thumb_bottom: int, floor_map: FloorOne | FloorTwo) -> int:
        maximum = self.max_map_scroll(floor_map)
        if maximum <= 0 or self.map_scrollbar_thumb_rect is None:
            return 0
        track_bottom, track_top = self.map_scrollbar_track_rect[1], self.map_scrollbar_track_rect[3]
        thumb_height = self.map_scrollbar_thumb_rect[3] - self.map_scrollbar_thumb_rect[1]
        usable_range = track_top - track_bottom - thumb_height
        if usable_range <= 0:
            return 0
        position = max(0, min(usable_range, thumb_bottom - track_bottom))
        return round(maximum * position / usable_range)

    def _draw_map_node(self, node: MapNode, scroll_y: int) -> None:
        x, y = node.x, node.y - scroll_y
        bottom = max(self.map_viewport[1], y - MAP_NODE_HALF_HEIGHT)
        top = min(self.map_viewport[3], y + MAP_NODE_HALF_HEIGHT)
        if bottom >= top:
            return
        self.map_node_rects[node.node_id] = (x - 90, bottom, x + 90, top)
        state = node.state
        index, label = MAP_SEALS[node.kind]
        cell = self.map_seals.w // 3
        seal_y = y + 12
        if state == "available":
            self.circle(x, seal_y, 46, SEPIA, filled=True)
            self.circle(x, seal_y, 44, GOLD, filled=True)
            self.circle(x, seal_y, 40, SEPIA)
        self.map_seals.opacify(0.70 if state == "locked" else 1.0)
        self.map_seals.clip_draw(
            (index % 3) * cell, (1 - index // 3) * cell, cell, cell,
            round(x * SCALE_X), round(seal_y * SCALE_Y),
            round(92 * min(SCALE_X, SCALE_Y)), round(92 * min(SCALE_X, SCALE_Y)),
        )
        self.map_seals.opacify(1.0)
        if state == "cleared":
            self.circle(x + 28, seal_y - 8, 12, (35, 90, 77), filled=True)
            self.line(x + 22, seal_y - 7, x + 26, seal_y - 12, TEXT)
            self.line(x + 26, seal_y - 12, x + 34, seal_y - 2, TEXT)
        self.image_stretched(self.map_nameplate, x - 90, y - 58, 180, 55)
        self.text(x, y - 22, label, 21, SEPIA, centered=True)
        status = {"available": "진행 가능", "cleared": "완료", "locked": "잠김"}[state]
        self.text(x, y - 40, f"{node.title} · {status}", 14, SEPIA, centered=True)

    def _draw_deck_preview(self, character_id: str, deck_cards: list[SkillCard] | None) -> None:
        data = character_info(character_id)
        cards = deck_cards if deck_cards is not None else starter_deck(character_id)
        self.panel(330, 160, 1080, 640, (18, 24, 37), GOLD)
        self.text(870, 756, f"{data['name']} · 스킬 덱", 25, data["accent"], centered=True)
        self.text(870, 720, f"카드 {len(cards)}장", 13, MUTED, centered=True)
        close = self.deck_preview_close_rect
        self.panel(close[0], close[1], close[2] - close[0], close[3] - close[1], PANEL_LIGHT, GOLD)
        self.text((close[0] + close[2]) / 2, (close[1] + close[3]) / 2, "닫기", 13, GOLD, centered=True)
        card_width = 164
        card_height = round(card_width * 188 / 140)
        card_gap = 18
        row_count = max(1, (len(cards) + 4) // 5)
        for index, card in enumerate(cards):
            row = index // 5
            row_start = row * 5
            row_items = min(5, len(cards) - row_start)
            total_width = card_width * row_items + card_gap * (row_items - 1)
            first_x = 870 - total_width / 2
            card_x = first_x + (index - row_start) * (card_width + card_gap)
            card_y = 360 if row_count == 1 else (455 if row == 0 else 207)
            center_x = card_x + card_width / 2
            center_y = card_y + card_height / 2
            content_scale = card_height / 188
            self._draw_card_rect(center_x, center_y, card_width, card_height, (31, 37, 50), inset=8)
            self._draw_card_illustration(
                character_id, card, center_x, center_y, card_width, card_height
            )
            self.text(center_x, card_y + card_height - 22 * content_scale, card.name, round(13 * content_scale), GOLD, centered=True)
            lines = self._card_description_lines(card)
            description_y = card_y + (58 if len(lines) > 1 else 51) * content_scale
            for line_index, line in enumerate(lines):
                self.text(center_x, description_y - line_index * 14 * content_scale, line, round(11 * content_scale), TEXT, centered=True)
            effect_color = MINT if card.status_key else MUTED
            self.text(center_x, card_y + 20 * content_scale, f"×{card.power:.2f} · {card.short_effect()}", round(10 * content_scale), effect_color, centered=True)
            self.image(self.card_frames[character_id], center_x, center_y, card_width, card_height)

    def toggle_deck_preview(self, character_id: str) -> None:
        self.deck_preview_character_id = None if self.deck_preview_character_id == character_id else character_id

    def close_deck_preview(self) -> None:
        self.deck_preview_character_id = None

    def draw_reward_choice(
        self,
        character_id: str,
        reward_options: list[tuple[str, SkillCard]],
        cursor: int,
        coins: int = 0,
        floor_number: int = 1,
    ) -> None:
        self._clear_page()
        background = self.floor2_battle_background if floor_number >= 2 else self.battle_background
        background.draw(WIDTH // 2, HEIGHT // 2, WIDTH, HEIGHT)
        self.panel(110, 140, 1220, 680, (18, 24, 37), GOLD)
        data = character_info(character_id)
        self.text(720, 777, "전투 승리 · 스킬 보상", 29, GOLD, centered=True)
        self.text(1180, 777, f"코인 {coins}", 16, GOLD, centered=True)
        self.text(720, 738, "추가할 적 스킬을 선택하세요", 16, TEXT, centered=True)
        self.reward_choice_rects.clear()
        if not reward_options:
            self.text(720, 475, "선택할 스킬이 없습니다.", 18, MUTED, centered=True)
            p2d.update_canvas()
            return

        card_width = min(220, (1120 - 24 * (len(reward_options) - 1)) // len(reward_options))
        card_height = round(card_width * 188 / 140)
        card_gap = 24
        total_width = card_width * len(reward_options) + card_gap * (len(reward_options) - 1)
        first_x = 720 - total_width / 2
        card_y = 320
        content_scale = card_height / 188
        for index, (source_name, card) in enumerate(reward_options):
            card_x = first_x + index * (card_width + card_gap)
            center_x = card_x + card_width / 2
            center_y = card_y + card_height / 2
            rect = (round(card_x), card_y, round(card_x + card_width), card_y + card_height)
            self.reward_choice_rects.append(rect)
            if index == cursor:
                self._draw_card_rect(center_x, center_y, card_width, card_height, GOLD, inset=-5, filled=False)
            self._draw_card_rect(center_x, center_y, card_width, card_height, (31, 37, 50), inset=8)
            self._draw_card_illustration(
                character_id, card, center_x, center_y, card_width, card_height
            )
            self.text(center_x, card_y + card_height + 18, source_name, 13, MUTED, centered=True)
            self.text(center_x, card_y + card_height - 22 * content_scale, card.name, round(13 * content_scale), GOLD, centered=True)
            lines = self._card_description_lines(card)
            description_y = card_y + (58 if len(lines) > 1 else 51) * content_scale
            for line_index, line in enumerate(lines):
                self.text(center_x, description_y - line_index * 14 * content_scale, line, round(11 * content_scale), TEXT, centered=True)
            effect_color = MINT if card.status_key else MUTED
            self.text(center_x, card_y + 20 * content_scale, f"×{card.power * PLAYER_CARD_DAMAGE_SCALE:.2f} · {card.short_effect()}", round(10 * content_scale), effect_color, centered=True)
            self.image(self.card_frames[character_id], center_x, center_y, card_width, card_height)
        self.text(720, 205, "카드에 커서를 올려 강조 표시 · 클릭하여 선택", 14, MUTED, centered=True)
        p2d.update_canvas()

    def reward_choice_at(self, x: int, y: int) -> int | None:
        for index, rect in enumerate(self.reward_choice_rects):
            if self._inside(x, y, rect):
                return index
        return None

    def draw_reward_character_choice(
        self,
        card: SkillCard,
        source_name: str,
        party: list[PlayerCharacter],
        cursor: int,
        coins: int = 0,
        floor_number: int = 1,
    ) -> None:
        self._clear_page()
        background = self.floor2_battle_background if floor_number >= 2 else self.battle_background
        background.draw(WIDTH // 2, HEIGHT // 2, WIDTH, HEIGHT)
        self.panel(110, 140, 1220, 680, (18, 24, 37), GOLD)
        self.text(720, 777, "전투 승리 · 카드 추가 대상", 29, GOLD, centered=True)
        self.text(1180, 777, f"코인 {coins}", 16, GOLD, centered=True)
        self.text(720, 738, "선택한 스킬을 추가할 캐릭터를 고르세요", 16, TEXT, centered=True)

        preview_rect = (150, 245, 500, 700)
        self.panel(
            preview_rect[0],
            preview_rect[1],
            preview_rect[2] - preview_rect[0],
            preview_rect[3] - preview_rect[1],
            PANEL,
            LINE,
        )
        self.text(325, 665, f"{source_name}에게서 획득", 15, CORAL, centered=True)
        card_width = 178
        card_height = round(card_width * 188 / 140)
        card_x, card_y = 236, 359
        center_x = card_x + card_width / 2
        center_y = card_y + card_height / 2
        content_scale = card_height / 188
        self._draw_card_rect(center_x, center_y, card_width, card_height, (31, 37, 50), inset=8)
        self.text(
            center_x,
            card_y + card_height - 22 * content_scale,
            card.name,
            round(13 * content_scale),
            CORAL,
            centered=True,
        )
        description_lines = self._card_description_lines(card)
        description_y = card_y + (58 if len(description_lines) > 1 else 51) * content_scale
        for line_index, line in enumerate(description_lines):
            self.text(
                center_x,
                description_y - line_index * 14 * content_scale,
                line,
                round(11 * content_scale),
                TEXT,
                centered=True,
            )
        effect_color = MINT if card.status_key else MUTED
        self.text(
            center_x,
            card_y + 20 * content_scale,
            f"×{card.power:.2f} · {card.short_effect()}",
            round(10 * content_scale),
            effect_color,
            centered=True,
        )
        self.image(self.card_frames["enemy"], center_x, center_y, card_width, card_height)

        count = len(party)
        if count == 1:
            slots = [(740, 350)]
        elif count == 2:
            slots = [(555, 440), (935, 440)]
        elif count == 3:
            slots = [(555, 440), (935, 440), (740, 205)]
        else:
            slots = [(555, 440), (935, 440), (555, 205), (935, 205)]
        self.reward_character_rects.clear()
        for index, hero in enumerate(party):
            slot_x, slot_y = slots[index]
            rect = (slot_x, slot_y, slot_x + 350, slot_y + 210)
            self.reward_character_rects.append(rect)
            hovered = index == cursor
            edge = GOLD if hovered else hero.accent
            fill = (48, 45, 40) if hovered else PANEL
            self.panel(rect[0], rect[1], rect[2] - rect[0], rect[3] - rect[1], fill, edge)
            self.image(self.portraits[hero.unit_id], rect[0] + 78, rect[1] + 112, 74, 111)
            short_name = hero.name.split(" · ", 1)[0]
            self.text(rect[0] + 145, rect[1] + 166, short_name, 16, hero.accent)
            self.text(rect[2] - 16, rect[1] + 166, f"Lv.{hero.level}", 12, MUTED)
            self.text(rect[0] + 145, rect[1] + 130, f"HP  {hero.hp}/{hero.max_hp}", 13, TEXT)
            self.text(rect[0] + 145, rect[1] + 105, f"ATK  {hero.attack}", 13, TEXT)
            self.text(rect[0] + 145, rect[1] + 80, f"SPD  {hero.effective_speed()}", 13, TEXT)
            deck_count = len(hero.deck) + len(hero.hand) + len(hero.discard)
            self.text(rect[0] + 145, rect[1] + 58, f"덱 {deck_count}/{MAX_DECK_SIZE}", 11, GOLD)
            self.text(rect[0] + 145, rect[1] + 36, "이 캐릭터의 덱에 추가", 11, GOLD if hovered else MUTED)

        self.text(720, 176, "캐릭터에 커서를 올려 강조 표시 · 클릭하여 덱에 추가", 14, MUTED, centered=True)
        p2d.update_canvas()

    def reward_character_at(self, x: int, y: int) -> int | None:
        for index, rect in enumerate(self.reward_character_rects):
            if self._inside(x, y, rect):
                return index
        return None

    def draw_card_replacement(
        self,
        hero: PlayerCharacter,
        new_card: SkillCard,
        source_name: str,
        deck_cards: list[SkillCard],
        cursor: int,
        floor_number: int = 1,
        can_return_to_recipients: bool = True,
    ) -> None:
        self._clear_page()
        background = self.floor2_battle_background if floor_number >= 2 else self.battle_background
        background.draw(WIDTH // 2, HEIGHT // 2, WIDTH, HEIGHT)
        self.panel(38, 85, 1364, 790, (18, 24, 37), GOLD)
        self.text(720, 835, "덱 한도 도달 · 교체할 카드 선택", 26, GOLD, centered=True)
        self.text(720, 800, f"{hero.name}의 덱에서 카드 1장을 빼고 {new_card.name}을 추가합니다.  ({MAX_DECK_SIZE}장 제한)", 14, TEXT, centered=True)

        preview_rect = (72, 280, 312, 710)
        self.panel(preview_rect[0], preview_rect[1], preview_rect[2] - preview_rect[0], preview_rect[3] - preview_rect[1], PANEL_LIGHT, LINE)
        self.text(192, 675, f"{source_name}에게서 획득", 13, CORAL, centered=True)
        card_width = 170
        card_height = round(card_width * 188 / 140)
        card_x, card_y = 107, 345
        center_x = card_x + card_width / 2
        center_y = card_y + card_height / 2
        scale = card_height / 188
        self._draw_card_rect(center_x, center_y, card_width, card_height, (31, 37, 50), inset=8)
        self.text(center_x, card_y + card_height - 22 * scale, new_card.name, round(13 * scale), GOLD, centered=True)
        lines = textwrap.wrap(new_card.description, width=8)[:2] or [new_card.description]
        description_y = card_y + (58 if len(lines) > 1 else 51) * scale
        for index, line in enumerate(lines):
            self.text(center_x, description_y - index * 14 * scale, line, round(11 * scale), TEXT, centered=True)
        self.text(center_x, card_y + 20 * scale, f"×{new_card.power:.2f} · {new_card.short_effect()}", round(10 * scale), MINT, centered=True)
        self.image(self.card_frames["enemy"], center_x, center_y, card_width, card_height)

        self.card_replace_rects.clear()
        card_width = 164
        card_height = round(card_width * 188 / 140)
        card_gap_x = 18
        card_gap_y = 14
        grid_width = card_width * 3 + card_gap_x * 2
        first_x = 350 + (1050 - grid_width) // 2
        first_y = 125
        for index, card in enumerate(deck_cards):
            row, column = divmod(index, 3)
            x = first_x + column * (card_width + card_gap_x)
            y = first_y + (2 - row) * (card_height + card_gap_y)
            rect = (x, y, x + card_width, y + card_height)
            self.card_replace_rects.append(rect)
            if index == cursor:
                self._draw_card_rect(x + card_width / 2, y + card_height / 2, card_width + 8, card_height + 8, GOLD, filled=False)
            self._draw_skill_card_face(hero, card, x + card_width / 2, y + card_height / 2, card_width / CARD_W)

        self.panel(*self.card_replace_cancel_rect[:2], self.card_replace_cancel_rect[2] - self.card_replace_cancel_rect[0], self.card_replace_cancel_rect[3] - self.card_replace_cancel_rect[1], PANEL_LIGHT, LINE)
        cancel_label = "뒤로가기" if can_return_to_recipients else "교환 포기"
        self.text((self.card_replace_cancel_rect[0] + self.card_replace_cancel_rect[2]) / 2, 135, cancel_label, 15, MUTED, centered=True)
        instruction = "교체할 기존 카드를 클릭하세요"
        if not can_return_to_recipients:
            instruction += " · 또는 교환 포기"
        self.text(875, 112, instruction, 13, MUTED, centered=True)
        p2d.update_canvas()

    def card_replace_at(self, x: int, y: int) -> int | None:
        for index, rect in enumerate(self.card_replace_rects):
            if self._inside(x, y, rect):
                return index
        return None

    def card_replace_cancel_clicked(self, x: int, y: int) -> bool:
        return self._inside(x, y, self.card_replace_cancel_rect)

    def draw_shop(
        self,
        coins: int,
        offers: list[ShopOffer],
        party: list[PlayerCharacter],
        relic_ids: list[str],
        reroll_cost: int,
        notice: str = "",
    ) -> None:
        self._clear_page()
        self.text(720, 900, "떠돌이 상점", 32, GOLD, centered=True)
        self.text(1295, 900, f"보유 코인  {coins}", 18, GOLD, centered=True)
        self.text(720, 855, f"동행자 {len(party)}/4   ·   유물 {len(relic_ids)}/{MAX_RELICS}", 15, MUTED, centered=True)
        self.panel(80, 246, 1280, 550, PANEL, LINE)
        self.shop_offer_rects.clear()
        centers = (320, 720, 1120)
        category_names = {"recruit": "영입", "upgrade": "강화", "relic": "유물", "heal": "회복"}
        accents = {"recruit": BLUE, "upgrade": MINT, "relic": GOLD, "heal": CORAL}
        for index, offer in enumerate(offers):
            center_x = centers[index]
            rect = (center_x - 175, 310, center_x + 175, 755)
            border = accents[offer.category] if offer.available and not offer.sold else LINE
            fill = PANEL_LIGHT if offer.available and not offer.sold else (24, 29, 41)
            self.panel(rect[0], rect[1], rect[2] - rect[0], rect[3] - rect[1], fill, border)
            self.text(center_x, 710, category_names[offer.category], 17, accents[offer.category], centered=True)
            self.text(center_x, 655, offer.title, 20, TEXT if offer.available else MUTED, centered=True)
            lines = textwrap.wrap(offer.description, width=22)[:4] or [offer.description]
            for line_index, line in enumerate(lines):
                self.text(center_x, 575 - line_index * 26, line, 14, MUTED, centered=True)
            if offer.sold:
                self.text(center_x, 430, "구매 완료", 19, MINT, centered=True)
                self.shop_offer_rects.append((0, 0, 0, 0))
            elif offer.available:
                self.text(center_x, 405, f"가격  {offer.price} 코인", 17, GOLD, centered=True)
                button = (center_x - 124, 326, center_x + 124, 378)
                self.panel(*button[:2], button[2] - button[0], button[3] - button[1], (52, 48, 42), GOLD)
                self.text(center_x, 343, "구매", 17, GOLD, centered=True)
                self.shop_offer_rects.append(button)
            else:
                self.text(center_x, 405, "구매할 수 없음", 16, MUTED, centered=True)
                self.shop_offer_rects.append((0, 0, 0, 0))

        self.panel(*self.shop_reroll_rect[:2], self.shop_reroll_rect[2] - self.shop_reroll_rect[0], self.shop_reroll_rect[3] - self.shop_reroll_rect[1], PANEL_LIGHT, LINE)
        self.text(
            (self.shop_reroll_rect[0] + self.shop_reroll_rect[2]) / 2,
            140,
            f"상품 재배치 · {reroll_cost} 코인",
            15,
            GOLD,
            centered=True,
        )
        self.panel(*self.shop_leave_rect[:2], self.shop_leave_rect[2] - self.shop_leave_rect[0], self.shop_leave_rect[3] - self.shop_leave_rect[1], (52, 48, 42), GOLD)
        self.text(
            (self.shop_leave_rect[0] + self.shop_leave_rect[2]) / 2,
            140,
            "상점 나가기",
            16,
            GOLD,
            centered=True,
        )
        relic_names = " · ".join(RELIC_BY_ID[relic_id].name for relic_id in relic_ids) or "없음"
        self.text(720, 214, f"보유 유물: {relic_names}", 12, MINT, centered=True)
        self.text(720, 94, notice or "상품은 각 분류에서 하나씩 무작위로 제시됩니다.", 13, MUTED if not notice else GOLD, centered=True)
        p2d.update_canvas()

    def draw_level_up(
        self,
        hero: PlayerCharacter,
        selected_stat: str | None,
        spinning: bool,
        number: int,
        roll_range: tuple[int, int],
        coins: int,
    ) -> None:
        self._clear_page()
        self.panel(215, 192, 1010, 610, (20, 27, 41), GOLD)
        self.text(720, 748, f"{hero.name} · 레벨 강화", 28, GOLD, centered=True)
        self.text(720, 706, f"Lv.{hero.level} → Lv.{hero.level + 1}  ·  전체 스탯 +10%p", 17, TEXT, centered=True)
        self.text(720, 672, f"코인 {coins}  ·  추가 강화 수치 {roll_range[0]}~{roll_range[1]} 룰렛", 14, MUTED, centered=True)
        stat_labels = {"hp": "최대 체력", "attack": "공격력", "speed": "속도"}
        self.level_up_stat_rects.clear()
        for stat, center_x in (("hp", 405), ("attack", 720), ("speed", 1035)):
            rect = (center_x - 130, 450, center_x + 130, 580)
            self.level_up_stat_rects[stat] = rect
            selected = stat == selected_stat
            self.panel(
                rect[0], rect[1], rect[2] - rect[0], rect[3] - rect[1],
                (52, 48, 42) if selected else PANEL_LIGHT,
                GOLD if selected else LINE,
            )
            value = hero.max_hp if stat == "hp" else hero.attack if stat == "attack" else hero.speed
            self.text(center_x, 530, stat_labels[stat], 18, GOLD if selected else TEXT, centered=True)
            self.text(center_x, 492, f"현재 {value}", 14, MUTED, centered=True)
        spinning_label = f"룰렛  {number}" if spinning else "룰렛 시작"
        self.panel(*self.level_up_spin_rect[:2], self.level_up_spin_rect[2] - self.level_up_spin_rect[0], self.level_up_spin_rect[3] - self.level_up_spin_rect[1], (52, 48, 42), GOLD)
        self.text(720, 279, spinning_label, 20, GOLD if selected_stat else MUTED, centered=True)
        instruction = "SPACE를 눌러 룰렛을 멈추세요" if spinning else "스탯을 선택한 뒤 룰렛을 시작하세요"
        self.text(720, 228, instruction, 14, MUTED, centered=True)
        p2d.update_canvas()

    def draw_level_up_result(
        self,
        hero_name: str,
        stat_name: str,
        roll: int,
        before: dict[str, int],
        after: dict[str, int],
    ) -> None:
        self._clear_page()
        self.panel(250, 120, 940, 690, (20, 27, 41), GOLD)
        self.text(720, 728, "강화 완료", 30, GOLD, centered=True)
        self.text(720, 686, f"{hero_name} · {stat_name} +{roll}", 16, TEXT, centered=True)
        self.text(780, 630, "강화 전", 15, MUTED, centered=True)
        self.text(1000, 630, "강화 후", 15, MINT, centered=True)

        rows = (
            ("레벨", "level"),
            ("현재 체력", "hp"),
            ("최대 체력", "max_hp"),
            ("공격력", "attack"),
            ("속도", "speed"),
        )
        for index, (label, key) in enumerate(rows):
            y = 575 - index * 57
            self.line(390, y - 23, 1050, y - 23, LINE)
            self.text(430, y, label, 16, TEXT)
            self.text(780, y, str(before[key]), 16, MUTED, centered=True)
            increase = after[key] - before[key]
            after_text = f"{after[key]}  (+{increase})" if increase > 0 else str(after[key])
            self.text(1000, y, after_text, 16, MINT, centered=True)

        rect = self.level_up_result_confirm_rect
        self.text(720, 275, "확인 버튼을 누르거나 Enter / Space를 누르세요", 13, MUTED, centered=True)
        self.panel(rect[0], rect[1], rect[2] - rect[0], rect[3] - rect[1], (52, 48, 42), GOLD)
        self.text((rect[0] + rect[2]) / 2, rect[1] + 35, "확인", 20, GOLD, centered=True)
        p2d.update_canvas()

    def draw_relic_replacement(
        self, relic_ids: list[str], new_relic_id: str, coins: int, price: int,
        is_reward: bool = False,
    ) -> None:
        self._clear_page()
        relic = RELIC_BY_ID[new_relic_id]
        self.panel(170, 185, 1100, 625, (20, 27, 41), GOLD)
        title = f"유물 보상 · {relic.name}" if is_reward else f"유물 보관 한도 · {relic.name} 획득"
        self.text(720, 745, title, 27, GOLD, centered=True)
        instruction = "교체할 유물을 선택하세요. 교체는 무료입니다." if is_reward else f"보유 한도에 도달했습니다. 교체할 유물을 선택하세요.  ·  {price} 코인"
        self.text(720, 701, instruction, 15, TEXT, centered=True)
        self.relic_replace_rects.clear()
        centers = (360, 720, 1080)
        for index, relic_id in enumerate(relic_ids):
            center_x = centers[index % len(centers)]
            row = index // len(centers)
            bottom = 390 if row == 0 else 260
            rect = (center_x - 150, bottom, center_x + 150, bottom + 100)
            self.relic_replace_rects.append(rect)
            old_relic = RELIC_BY_ID[relic_id]
            self.panel(rect[0], rect[1], rect[2] - rect[0], rect[3] - rect[1], PANEL_LIGHT, LINE)
            self.text(center_x, bottom + 66, old_relic.name, 17, TEXT, centered=True)
            self.text(center_x, bottom + 34, textwrap.shorten(old_relic.description, width=28), 11, MUTED, centered=True)
        self.panel(*self.relic_replace_cancel_rect[:2], self.relic_replace_cancel_rect[2] - self.relic_replace_cancel_rect[0], self.relic_replace_cancel_rect[3] - self.relic_replace_cancel_rect[1], PANEL_LIGHT, LINE)
        self.text(720, 176, "보상 포기" if is_reward else "취소", 15, MUTED, centered=True)
        self.text(720, 110, f"보유 코인 {coins}", 14, GOLD, centered=True)
        p2d.update_canvas()

    def shop_offer_at(self, x: int, y: int) -> int | None:
        for index, rect in enumerate(self.shop_offer_rects):
            if rect != (0, 0, 0, 0) and self._inside(x, y, rect):
                return index
        return None

    def shop_reroll_clicked(self, x: int, y: int) -> bool:
        return self._inside(x, y, self.shop_reroll_rect)

    def shop_leave_clicked(self, x: int, y: int) -> bool:
        return self._inside(x, y, self.shop_leave_rect)

    def level_up_stat_at(self, x: int, y: int) -> str | None:
        for stat, rect in self.level_up_stat_rects.items():
            if self._inside(x, y, rect):
                return stat
        return None

    def level_up_spin_clicked(self, x: int, y: int) -> bool:
        return self._inside(x, y, self.level_up_spin_rect)

    def level_up_result_confirm_clicked(self, x: int, y: int) -> bool:
        return self._inside(x, y, self.level_up_result_confirm_rect)

    def relic_replace_at(self, x: int, y: int) -> int | None:
        for index, rect in enumerate(self.relic_replace_rects):
            if self._inside(x, y, rect):
                return index
        return None

    def relic_replace_cancel_clicked(self, x: int, y: int) -> bool:
        return self._inside(x, y, self.relic_replace_cancel_rect)

    def draw_floor_complete(self, coins: int = 0, floor_number: int = 1) -> None:
        self._clear_page()
        self.circle(720, 565, 190, (47, 43, 38), filled=True)
        is_final = floor_number >= 2
        self.text(720, 620, "2층 클리어" if is_final else "1층 클리어", 38, GOLD, centered=True)
        self.text(720, 558, "프로토타입을 완료했습니다." if is_final else "2층으로 진입할 준비가 되었습니다.", 17, TEXT, centered=True)
        self.text(720, 518, f"보유 코인 {coins}", 15, GOLD, centered=True)
        self.panel(self.complete_rect[0], self.complete_rect[1], self.complete_rect[2] - self.complete_rect[0], self.complete_rect[3] - self.complete_rect[1], (52, 48, 42), GOLD)
        self.text(720, 278, "타이틀로" if is_final else "2층으로 진입", 20, GOLD, centered=True)
        p2d.update_canvas()

    def title_start_clicked(self, x: int, y: int) -> bool:
        return self._inside(x, y, self.start_rect)

    def selected_character_at(self, x: int, y: int) -> str | None:
        for character_id, rect in self.character_rects.items():
            if self._inside(x, y, rect):
                return character_id
        return None

    def confirm_selection_clicked(self, x: int, y: int) -> bool:
        return self._inside(x, y, self.confirm_rect)

    def map_character_at(self, x: int, y: int) -> str | None:
        for character_id, rect in self.map_character_rects.items():
            if self._inside(x, y, rect):
                return character_id
        return None

    def map_deck_preview_close_clicked(self, x: int, y: int) -> bool:
        return self._inside(x, y, self.deck_preview_close_rect)

    def map_node_at(self, x: int, y: int, floor_map: FloorOne | FloorTwo) -> str | None:
        for node_id, rect in self.map_node_rects.items():
            if floor_map.nodes[node_id].unlocked and not floor_map.nodes[node_id].cleared and self._inside(x, y, rect):
                return node_id
        return None

    def map_restart_clicked(self, x: int, y: int) -> bool:
        return self._inside(x, y, self.map_restart_rect)

    def floor_complete_clicked(self, x: int, y: int) -> bool:
        return self._inside(x, y, self.complete_rect)
