"""Pico2D rendering and keyboard controls for the combat stage."""

from __future__ import annotations

import os
from pathlib import Path

import pico2d as p2d

from battle import Battle
from units import Enemy, PlayerCharacter


DESIGN_WIDTH, DESIGN_HEIGHT = 1440, 960
WIDTH, HEIGHT = 1280, 720
SCALE_X = WIDTH / DESIGN_WIDTH
SCALE_Y = HEIGHT / DESIGN_HEIGHT
CARD_W = 170
CARD_H = 145

INK = (13, 17, 28)
PANEL = (25, 31, 47)
PANEL_LIGHT = (34, 42, 60)
LINE = (64, 73, 92)
TEXT = (235, 236, 231)
MUTED = (152, 163, 178)
GOLD = (231, 190, 105)
MINT = (112, 211, 178)
CORAL = (231, 129, 119)
BLUE = (116, 172, 226)


class BattleScreen:
    def __init__(self, asset_root: Path) -> None:
        self.asset_root = asset_root
        self.font_file = self._find_font()
        self.fonts = {size: p2d.load_font(self.font_file, size) for size in (9, 10, 11, 12, 13, 14, 15, 16, 18, 20, 22, 24, 26, 28)}
        self.textures: dict[tuple[str, tuple[int, int, int], int], p2d.Image] = {}
        self.portraits: dict[str, p2d.Image] = {}
        for character_id in "ABCD":
            path = asset_root / "images" / f"{character_id}.png"
            self.portraits[character_id] = p2d.load_image(str(path))
        self.action_cursor = 0
        self.target_enemy_id: str | None = None
        self.focus_actor_id: str | None = None

    @staticmethod
    def _find_font() -> str:
        windows = Path(os.environ.get("WINDIR", r"C:\Windows"))
        for name in ("malgun.ttf", "malgunsl.ttf", "arial.ttf"):
            path = windows / "Fonts" / name
            if path.exists():
                return str(path)
        raise FileNotFoundError("Windows Korean font not found (expected C:\\Windows\\Fonts\\malgun.ttf).")

    def _text_image(self, text: str, color: tuple[int, int, int], size: int) -> p2d.Image:
        size = max(9, round(size * 0.76))
        key = (text, color, size)
        image = self.textures.get(key)
        if image:
            return image
        if size not in self.fonts:
            self.fonts[size] = p2d.load_font(self.font_file, size)
        font = self.fonts[size]
        surface = p2d.TTF_RenderUTF8_Blended(font.font, text.encode("utf-8"), p2d.SDL_Color(*color))
        if not surface:
            raise RuntimeError(f"Could not render text: {text}")
        texture = p2d.SDL_CreateTextureFromSurface(p2d.pico2d.renderer, surface)
        p2d.SDL_FreeSurface(surface)
        if not texture:
            raise RuntimeError(f"Could not create text texture: {text}")
        image = p2d.Image(texture)
        self.textures[key] = image
        return image

    def text(self, x: float, y: float, value: str, size: int = 16, color: tuple[int, int, int] = TEXT, centered: bool = False) -> None:
        if value == "":
            return
        image = self._text_image(str(value), color, size)
        center_x = x if centered else x + image.w / 2
        image.draw(center_x * SCALE_X, y * SCALE_Y, image.w, image.h)

    @staticmethod
    def rect(x: int, y: int, w: int, h: int, color: tuple[int, int, int], filled: bool = True) -> None:
        p2d.draw_rectangle(round(x * SCALE_X), round(y * SCALE_Y), round((x + w) * SCALE_X), round((y + h) * SCALE_Y), *color, filled=filled)

    @staticmethod
    def line(x1: int, y1: int, x2: int, y2: int, color: tuple[int, int, int]) -> None:
        p2d.draw_line(round(x1 * SCALE_X), round(y1 * SCALE_Y), round(x2 * SCALE_X), round(y2 * SCALE_Y), *color)

    @staticmethod
    def circle(x: int, y: int, radius: int, color: tuple[int, int, int], filled: bool = False) -> None:
        p2d.draw_circle(round(x * SCALE_X), round(y * SCALE_Y), round(radius * 0.8), *color, filled=filled)

    @staticmethod
    def image(image: p2d.Image, x: int, y: int, w: int, h: int) -> None:
        image.draw(round(x * SCALE_X), round(y * SCALE_Y), round(w * SCALE_X), round(h * SCALE_Y))

    def panel(self, x: int, y: int, w: int, h: int, fill: tuple[int, int, int] = PANEL, border: tuple[int, int, int] = LINE) -> None:
        self.rect(x, y, w, h, fill)
        self.rect(x, y, w, h, border, filled=False)

    def draw(self, battle: Battle, now: float) -> None:
        self._sync_focus(battle)
        p2d.clear_canvas()
        self.rect(0, 0, DESIGN_WIDTH, DESIGN_HEIGHT, INK)
        self._draw_header(battle)
        self._draw_order(battle)
        self._draw_battlefield(battle, now)
        self._draw_action_cards(battle)
        p2d.update_canvas()

    def _draw_header(self, battle: Battle) -> None:
        self.text(30, 922, "REDITUS ARCANUM", 34, TEXT)
        self.text(1214, 925, f"TURN  {battle.round:02d}", 22, GOLD)
        self.text(1215, 894, "BATTLE STAGE  /  PROTOTYPE", 14, MUTED)

    def _draw_chip(self, x: int, y: int, title: str, fill: tuple[int, int, int]) -> None:
        self.panel(x, y - 13, 55, 26, fill, fill)
        self.text(x + 27, y, title, 14, TEXT, centered=True)

    def _draw_order(self, battle: Battle) -> None:
        self.panel(28, 789, 1384, 75, PANEL)
        self.text(45, 842, "행동 순서", 16, GOLD)
        start_x = 262
        step = 183
        for index, entry in enumerate(battle.order):
            actor = entry.actor
            x = start_x + index * step
            active = index == battle.order_index and battle.phase not in ("victory", "defeat")
            border = GOLD if active else LINE
            fill = (58, 51, 42) if active else PANEL_LIGHT
            self.panel(x, 804, 164, 45, fill, border)
            color = actor.accent if actor.alive else MUTED
            label = actor.unit_id if actor.side == "player" else actor.name[:4]
            self.text(x + 11, 832, label, 14, color)
            self.text(x + 11, 813, f"SPD {actor.effective_speed()}", 12, MUTED)
            self.text(x + 133, 825, f"d{entry.die}", 12, GOLD if active else MUTED, centered=True)
            if not actor.alive:
                self.rect(x + 1, 805, 162, 43, INK)
                self.text(x + 82, 825, "DOWN", 12, MUTED, centered=True)

    def _draw_battlefield(self, battle: Battle, now: float) -> None:
        self.panel(28, 160, 1384, 618, (19, 25, 39), (54, 66, 86))
        self.text(48, 753, "전투", 16, MUTED)
        self.line(270, 187, 1170, 187, (44, 57, 77))
        self.panel(48, 205, 1344, 44, (24, 31, 46), (45, 55, 72))
        if battle.log_lines:
            self.text(64, 227, "전투 기록", 13, GOLD)
            self.text(154, 227, battle.log_lines[0][:80], 14, TEXT)

        hero_y = (700, 535, 370, 205)
        for hero, y in zip(battle.party, hero_y):
            self._draw_hero(hero, 150, y, battle)
        enemy_y = (585, 335)
        for enemy, y in zip(battle.enemies, enemy_y):
            self._draw_enemy(enemy, 1270, y, battle)

        if battle.phase in ("attack_timing", "defense_timing"):
            self._draw_timing(battle, now)
        elif battle.phase == "result":
            self._draw_result(battle)
        elif battle.phase == "victory":
            self._draw_end_card("전투 승리", "1층 맵으로 돌아갑니다.", True)
        elif battle.phase == "defeat":
            self._draw_end_card("전투 종료", "파티를 정비하고 다시 시도하세요.", False)
        elif battle.phase == "player" and battle.selected_card:
            card = battle.selected_card
            self.panel(458, 265, 470, 132, (27, 34, 50), GOLD)
            self.text(693, 355, card.name, 24, GOLD, centered=True)
            self.text(693, 318, card.description, 16, TEXT, centered=True)
            self.text(693, 286, "공격할 적을 선택하세요", 15, MUTED, centered=True)
            target = self._focused_enemy(battle)
            if target:
                target_index = battle.enemies.index(target)
                target_y = (585, 335)[min(target_index, 1)]
                self._draw_target_arrow(930, 478, 1170, target_y)

    def _draw_hero(self, hero: PlayerCharacter, x: int, y: int, battle: Battle) -> None:
        active = hero is battle.active
        border = GOLD if active else hero.accent
        glow = (34, 42, 57) if not active else (55, 51, 42)
        self.circle(x, y, 48, glow, filled=True)
        if hero.alive:
            self.circle(x, y, 49, border, filled=False)
            self.image(self.portraits[hero.unit_id], x, y, 72, 108)
        else:
            self.circle(x, y, 36, (70, 75, 86), filled=True)
            self.text(x, y, "DOWN", 14, MUTED, centered=True)
        self.text(x, y + 83, hero.name, 13, border, centered=True)
        self._bar(x - 54, y + 62, 108, 6, hero.hp / hero.max_hp, hero.accent)
        self.text(x, y + 43, f"HP {hero.hp}/{hero.max_hp}", 10, MUTED, centered=True)
        if hero.unit_id == "D" and hero.perfect_stacks:
            self.text(x, y - 66, f"PERFECT +{hero.perfect_stacks}", 11, GOLD, centered=True)
        if hero.statuses.snapshot():
            first = hero.statuses.snapshot()[0]
            self._draw_chip(x - 28, y - 87, first.label, (99, 58, 70))

    def _draw_enemy(self, enemy: Enemy, x: int, y: int, battle: Battle) -> None:
        selected_target = enemy.unit_id == self.target_enemy_id and battle.phase == "player" and battle.selected_card
        target = selected_target or (enemy is battle.attack_target and battle.phase in ("attack_timing", "result"))
        radius_color = GOLD if target else enemy.accent
        if not enemy.alive:
            self.circle(x, y, 40, (72, 68, 81), filled=True)
            self.text(x, y, "DOWN", 14, MUTED, centered=True)
        else:
            self.circle(x, y, 65, radius_color, filled=False)
            self.circle(x, y, 52, (46, 40, 63), filled=True)
            self.circle(x, y, 36, enemy.accent, filled=True)
            self.circle(x, y, 25, (31, 25, 45), filled=True)
            self.circle(x, y, 14, (232, 203, 238), filled=True)
            for spoke in range(8):
                angle = spoke * 0.785398
                dx, dy = int(70 * __import__("math").cos(angle)), int(70 * __import__("math").sin(angle))
                self.line(x + dx, y + dy, x + int(dx * 1.22), y + int(dy * 1.22), enemy.accent)
        self.text(x, y - 92, enemy.name, 18, TEXT, centered=True)
        self._bar(x - 66, y - 113, 132, 9, enemy.hp / enemy.max_hp, CORAL)
        self.text(x, y - 136, f"HP {enemy.hp}/{enemy.max_hp} · ATK {enemy.attack} · SPD {enemy.speed}", 11, MUTED, centered=True)
        for i, effect in enumerate(enemy.statuses.snapshot()[:2]):
            self._draw_chip(x - 61 + i * 91, y - 163, effect.label, (110, 57, 68))

    def _bar(self, x: int, y: int, w: int, h: int, ratio: float, color: tuple[int, int, int]) -> None:
        self.rect(x, y, w, h, (43, 49, 62))
        self.rect(x, y, int(w * max(0, min(1, ratio))), h, color)

    def _draw_timing(self, battle: Battle, now: float) -> None:
        defending = battle.phase == "defense_timing"
        self.panel(454, 455, 532, 190, (24, 30, 46), GOLD if defending else (111, 179, 197))
        if defending:
            source = battle.incoming_source.name if battle.incoming_source else "적"
            skill = battle.incoming_skill.name if battle.incoming_skill else "공격"
            target = battle.incoming_target.name if battle.incoming_target else "아군"
            self.text(720, 612, f"{source} · {skill}", 22, CORAL, centered=True)
            self.text(720, 580, f"{target} 방어 · 입력 성공 시 피해 50% 감소", 15, TEXT, centered=True)
        else:
            card = battle.selected_card
            target = battle.attack_target.name if battle.attack_target else "적"
            self.text(720, 612, f"{card.name if card else '공격'}  →  {target}", 22, GOLD, centered=True)
            self.text(720, 580, "정확한 순간에 SPACE", 15, TEXT, centered=True)
        self._timing_gauge(battle, now)
        self.text(720, 478, "GOOD", 12, MUTED, centered=True)

    def _timing_gauge(self, battle: Battle, now: float) -> None:
        x, y, w, h = 520, 510, 400, 22
        self.rect(x, y, w, h, (51, 58, 72))
        center_x = x + int(battle.timing_center * w)
        good_px = int(battle.good_window * w)
        perfect_px = int(battle.perfect_window * w)
        self.rect(max(x, center_x - good_px), y, min(w, 2 * good_px), h, (158, 119, 60))
        self.rect(max(x, center_x - perfect_px), y, min(w, 2 * perfect_px), h, (77, 164, 130))
        marker_x = x + int(battle.timing_progress(now) * w)
        self.line(marker_x, y - 6, marker_x, y + h + 6, (248, 246, 229))
        self.text(720, 534, "PERFECT" if abs(marker_x - center_x) <= perfect_px else "", 12, MINT, centered=True)

    def _draw_result(self, battle: Battle) -> None:
        self.panel(500, 480, 440, 120, (26, 33, 48), battle.result_color)
        self.text(720, 545, battle.result_text, 25, battle.result_color, centered=True)
        self.text(720, 510, "다음 행동으로 넘어갑니다", 14, MUTED, centered=True)

    def _draw_end_card(self, title: str, message: str, victory: bool) -> None:
        border = GOLD if victory else CORAL
        self.panel(472, 462, 496, 174, (26, 32, 47), border)
        self.text(720, 585, title, 30, border, centered=True)
        self.text(720, 548, message, 16, TEXT, centered=True)
        if not victory:
            self.text(720, 503, "SPACE · 다시 전투", 16, GOLD, centered=True)

    def _draw_target_arrow(self, x1: int, y1: int, x2: int, y2: int) -> None:
        """Draw the target-selection arrow from the center to the enemy side."""
        self.line(x1, y1, x2, y2, GOLD)
        self.line(x2, y2, x2 - 28, y2 + 18, GOLD)
        self.line(x2, y2, x2 - 28, y2 - 18, GOLD)

    def _draw_action_cards(self, battle: Battle) -> None:
        """Show cards only while the active player is choosing a skill."""
        if battle.phase != "player" or not battle.active or battle.selected_card:
            return
        hero = battle.active
        action_indices = list(range(min(len(hero.hand), 5))) + [5]
        if self.action_cursor not in action_indices:
            self.action_cursor = action_indices[0]
        self.text(720, 730, f"{hero.name} · 사용할 스킬을 선택하세요", 16, hero.accent, centered=True)
        card_positions = ((460, 560), (680, 560), (460, 375), (680, 375), (460, 190))
        for card_index, (card, (card_x, card_y)) in enumerate(zip(hero.hand[:5], card_positions)):
            focused = card_index == self.action_cursor
            border = GOLD if focused else hero.accent
            fill = (53, 48, 39) if focused else (39, 45, 61)
            self.panel(card_x, card_y, CARD_W, CARD_H, fill, border)
            self.rect(card_x + 7, card_y + CARD_H - 8, CARD_W - 14, 4, hero.accent)
            self.text(card_x + CARD_W / 2, card_y + 112, card.name, 17, TEXT, centered=True)
            self.text(card_x + CARD_W / 2, card_y + 80, card.description[:15], 12, MUTED, centered=True)
            self.text(card_x + CARD_W / 2, card_y + 48, f"피해 배율 ×{card.power:.2f}", 13, GOLD, centered=True)
            self.text(card_x + CARD_W / 2, card_y + 24, card.short_effect(), 13, MINT if card.status_key else MUTED, centered=True)

        rest = (680, 190, 850, 335)
        rest_focused = self.action_cursor == 5
        self.panel(rest[0], rest[1], rest[2] - rest[0], rest[3] - rest[1], (57, 50, 41) if rest_focused else PANEL_LIGHT, GOLD if rest_focused else LINE)
        self.text((rest[0] + rest[2]) / 2, 267, "휴식", 18, GOLD if rest_focused else TEXT, centered=True)
        self.text((rest[0] + rest[2]) / 2, 237, "카드 보충", 12, MUTED, centered=True)

    def _sync_focus(self, battle: Battle) -> None:
        if battle.active and battle.active.unit_id != self.focus_actor_id:
            self.focus_actor_id = battle.active.unit_id
            self.action_cursor = 0
            self.target_enemy_id = None
        if battle.living_enemies and not any(enemy.unit_id == self.target_enemy_id for enemy in battle.living_enemies):
            self.target_enemy_id = battle.living_enemies[0].unit_id

    def _focused_enemy(self, battle: Battle) -> Enemy | None:
        living = battle.living_enemies
        if not living:
            return None
        for enemy in living:
            if enemy.unit_id == self.target_enemy_id:
                return enemy
        self.target_enemy_id = living[0].unit_id
        return living[0]

    def handle_key(self, battle: Battle, key: int) -> None:
        """Handle all battle decisions with Space and the arrow keys."""
        self._sync_focus(battle)
        if key == p2d.SDLK_SPACE:
            if battle.phase in ("attack_timing", "defense_timing"):
                battle.submit_timing()
            elif battle.phase == "defeat":
                battle.reset()
                self.focus_actor_id = None
            elif battle.phase == "player" and battle.active:
                hero = battle.active
                if battle.selected_card:
                    target = self._focused_enemy(battle)
                    if target:
                        battle.begin_attack(hero, battle.selected_card, target)
                elif self.action_cursor == 5:
                    battle.rest(hero)
                    self.action_cursor = 0
                elif 0 <= self.action_cursor < len(hero.hand):
                    battle.select_card(hero, hero.hand[self.action_cursor])
                    self._focused_enemy(battle)
            return

        if battle.phase != "player" or not battle.active:
            return
        self._sync_focus(battle)
        if key not in (p2d.SDLK_LEFT, p2d.SDLK_RIGHT, p2d.SDLK_UP, p2d.SDLK_DOWN):
            return

        if battle.selected_card:
            living = battle.living_enemies
            if not living:
                return
            focused = self._focused_enemy(battle)
            current = living.index(focused) if focused else 0
            step = -1 if key in (p2d.SDLK_LEFT, p2d.SDLK_UP) else 1
            self.target_enemy_id = living[(current + step) % len(living)].unit_id
            return

        hero = battle.active
        action_indices = list(range(min(len(hero.hand), 5))) + [5]
        coordinates = {0: (0, 0), 1: (1, 0), 2: (0, 1), 3: (1, 1), 4: (0, 2), 5: (1, 2)}
        if self.action_cursor not in action_indices:
            self.action_cursor = action_indices[0]
        col, row = coordinates[self.action_cursor]
        if key == p2d.SDLK_LEFT:
            candidates = [i for i in action_indices if coordinates[i][1] == row and coordinates[i][0] < col]
            if candidates:
                self.action_cursor = max(candidates, key=lambda i: coordinates[i][0])
        elif key == p2d.SDLK_RIGHT:
            candidates = [i for i in action_indices if coordinates[i][1] == row and coordinates[i][0] > col]
            if candidates:
                self.action_cursor = min(candidates, key=lambda i: coordinates[i][0])
        else:
            direction = -1 if key == p2d.SDLK_UP else 1
            candidates = [i for i in action_indices if (coordinates[i][1] - row) * direction > 0]
            if candidates:
                self.action_cursor = min(candidates, key=lambda i: (abs(coordinates[i][1] - row), abs(coordinates[i][0] - col)))

    @staticmethod
    def _inside(x: int, y: int, rect: tuple[int, int, int, int]) -> bool:
        return rect[0] <= x <= rect[2] and rect[1] <= y <= rect[3]
