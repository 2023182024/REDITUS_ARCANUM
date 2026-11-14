"""Pico2D rendering and mouse/keyboard controls for the combat stage."""

from __future__ import annotations

import math
import os
import time
import textwrap
from pathlib import Path

import pico2d as p2d

from battle import Battle
from units import Enemy, PlayerCharacter


DESIGN_WIDTH, DESIGN_HEIGHT = 1440, 960
WIDTH, HEIGHT = 1280, 720
SCALE_X = WIDTH / DESIGN_WIDTH
SCALE_Y = HEIGHT / DESIGN_HEIGHT
CARD_W = 140
CARD_H = 188
CARD_POSITIONS = ((450, 572), (620, 572), (450, 371), (620, 371), (450, 170))
REST_RECT = (620, 170, 760, 358)
ENEMY_POSITIONS = ((1270, 585), (1270, 335))
PARTY_POSITIONS = ((150, 700), (150, 535), (150, 370), (150, 205))
CANCEL_TARGET_RECT = (810, 268, 916, 310)
CARD_ANIMATION_DURATION = 0.38
CARD_ANIMATION_STAGGER = 0.06
CARD_HOVER_DURATION = 0.16
CARD_HOVER_SCALE = 0.10
CARD_HOVER_LIFT = 13
CARD_BACKGROUND_INSET = 8
CARD_FOCUS_PADDING = 3

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
        effect_files = {
            "A": "A_precision.png",
            "B": "B_twin_slash.png",
            "C": "C_arcane_burst.png",
            "D": "D_chain_flurry.png",
            "enemy": "enemy_impact.png",
            "perfect": "perfect_flash.png",
        }
        self.attack_effects = {
            key: p2d.load_image(str(asset_root / "images" / "effects" / filename))
            for key, filename in effect_files.items()
        }
        self.card_frames = {
            character_id: p2d.load_image(
                str(asset_root / "images" / "card_frames" / f"reditus_card_frame_{character_id.lower()}.png")
            )
            for character_id in "ABCD"
        }
        self.action_cursor = 0
        self.target_enemy_id: str | None = None
        self.focus_actor_id: str | None = None
        self.focus_round: int | None = None
        self.card_animation_started_at = 0.0
        self.hovered_card_index: int | None = None
        self.card_hover_progress: dict[int, float] = {}
        self.card_hover_last_at = time.monotonic()

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
        p2d.draw_circle(round(x * SCALE_X), round(y * SCALE_Y), round(radius * min(SCALE_X, SCALE_Y)), *color, filled=filled)

    @staticmethod
    def image(image: p2d.Image, x: int, y: int, w: int, h: int) -> None:
        scale = min(SCALE_X, SCALE_Y)
        image.draw(round(x * SCALE_X), round(y * SCALE_Y), round(w * scale), round(h * scale))

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
        self._draw_action_cards(battle, now)
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

        for hero, (hero_x, hero_y) in zip(battle.party, PARTY_POSITIONS):
            self._draw_hero(hero, hero_x, hero_y, battle)
        for enemy, (enemy_x, enemy_y) in zip(battle.enemies, ENEMY_POSITIONS):
            self._draw_enemy(enemy, enemy_x, enemy_y, battle)
        self._draw_attack_effect(battle, now)

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
            self.text(625, 286, "공격할 적을 선택하세요", 15, MUTED, centered=True)
            cancel = CANCEL_TARGET_RECT
            self.panel(cancel[0], cancel[1], cancel[2] - cancel[0], cancel[3] - cancel[1], PANEL_LIGHT, GOLD)
            self.text((cancel[0] + cancel[2]) / 2, (cancel[1] + cancel[3]) / 2, "취소", 14, GOLD, centered=True)
            target = self._focused_enemy(battle)
            if target:
                _, target_y = self._enemy_position(battle, target)
                self._draw_target_arrow(930, 478, 1170, target_y)

    def _draw_hero(self, hero: PlayerCharacter, x: int, y: int, battle: Battle) -> None:
        active = hero is battle.active
        border = GOLD if active else hero.accent
        glow = (34, 42, 57) if not active else (55, 51, 42)
        self.circle(x, y, 60, glow, filled=True)
        if hero.alive:
            self.circle(x, y, 60, border, filled=False)
            self.image(self.portraits[hero.unit_id], x, y, 110, 165)
        else:
            self.circle(x, y, 40, (70, 75, 86), filled=True)
            self.text(x, y, "DOWN", 14, MUTED, centered=True)
        info_x = 225
        self.text(info_x, y + 34, hero.name, 15, border)
        self._bar(info_x, y + 14, 178, 7, hero.hp / hero.max_hp, hero.accent)
        self.text(info_x, y - 10, f"HP {hero.hp}/{hero.max_hp}  ·  ATK {hero.attack}  SPD {hero.effective_speed()}", 11, MUTED)
        effects = hero.statuses.snapshot()[:1]
        for index, effect in enumerate(effects):
            self._draw_chip(info_x + 28 + index * 66, y - 28, effect.label, (99, 58, 70))
        if hero.unit_id == "D" and hero.perfect_stacks:
            self._draw_chip(info_x + 28 + len(effects) * 66, y - 28, f"P+{hero.perfect_stacks}", (99, 81, 43))

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
                dx, dy = int(70 * math.cos(angle)), int(70 * math.sin(angle))
                self.line(x + dx, y + dy, x + int(dx * 1.22), y + int(dy * 1.22), enemy.accent)
        self.text(x, y - 92, enemy.name, 18, TEXT, centered=True)
        self._bar(x - 66, y - 113, 132, 9, enemy.hp / enemy.max_hp, CORAL)
        self.text(x, y - 136, f"HP {enemy.hp}/{enemy.max_hp} · ATK {enemy.attack} · SPD {enemy.speed}", 11, MUTED, centered=True)
        for i, effect in enumerate(enemy.statuses.snapshot()[:2]):
            self._draw_chip(x - 61 + i * 91, y - 163, effect.label, (110, 57, 68))

    def _draw_attack_effect(self, battle: Battle, now: float) -> None:
        effect = battle.attack_effect
        if not effect:
            return
        elapsed = now - effect.started_at
        duration = 0.62
        if elapsed < 0 or elapsed > duration:
            return

        units = (*battle.party, *battle.enemies)
        source = next((unit for unit in units if unit.unit_id == effect.source_id), None)
        target = next((unit for unit in units if unit.unit_id == effect.target_id), None)
        if not source or not target:
            return

        sprite_key = source.unit_id if source.side == "player" else "enemy"
        sprite = self.attack_effects[sprite_key]
        progress = max(0.0, min(1.0, elapsed / duration))
        eased = 1.0 - (1.0 - progress) ** 3
        scale = (0.58 + 0.55 * eased) * (1.16 if effect.quality == "PERFECT" else 1.0)
        opacity = (1.0 - progress) ** 1.35
        dimensions = {
            "A": (260, 174),
            "B": (214, 214),
            "C": (200, 200),
            "D": (218, 218),
            "enemy": (185, 185),
        }
        width, height = dimensions[sprite_key]
        x, y = self._unit_position(battle, target)
        sprite.opacify(opacity)
        self.image(sprite, x, y, round(width * scale), round(height * scale))
        sprite.opacify(1.0)

        if effect.quality == "PERFECT":
            flash = self.attack_effects["perfect"]
            flash_progress = min(1.0, elapsed / 0.34)
            flash_scale = 0.42 + 0.82 * flash_progress
            flash.opacify(max(0.0, 1.0 - flash_progress))
            self.image(flash, x, y, round(124 * flash_scale), round(124 * flash_scale))
            flash.opacify(1.0)

        number_y = y + 76 + min(22, elapsed * 42)
        number_color = (255, 226, 149) if effect.quality == "PERFECT" else (242, 238, 232)
        self.text(x, number_y, f"-{effect.damage}", 22, number_color, centered=True)

    @staticmethod
    def _unit_position(battle: Battle, unit) -> tuple[int, int]:
        if unit.side == "player":
            index = battle.party.index(unit)
            return PARTY_POSITIONS[min(index, len(PARTY_POSITIONS) - 1)]
        index = battle.enemies.index(unit)
        return ENEMY_POSITIONS[min(index, len(ENEMY_POSITIONS) - 1)]

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
        """Draw only the arrowhead that marks the selected target."""
        self.line(x2, y2, x2 - 28, y2 + 18, GOLD)
        self.line(x2, y2, x2 - 28, y2 - 18, GOLD)

    def _draw_action_cards(self, battle: Battle, now: float) -> None:
        """Draw portrait skill cards and smoothly enlarge the card under the pointer."""
        if battle.phase != "player" or not battle.active or battle.selected_card:
            return
        hero = battle.active
        action_indices = list(range(min(len(hero.hand), 5))) + [5]
        if self.action_cursor not in action_indices:
            self.action_cursor = action_indices[0]
        self.text(720, 773, f"{hero.name} · 사용할 스킬을 선택하세요", 14, hero.accent, centered=True)
        hero_index = battle.party.index(hero)
        origin_x, origin_y = PARTY_POSITIONS[min(hero_index, len(PARTY_POSITIONS) - 1)]
        card_entries = list(enumerate(zip(hero.hand[:5], CARD_POSITIONS)))
        if self.hovered_card_index is not None:
            card_entries.sort(key=lambda entry: entry[0] == self.hovered_card_index)

        hover_delta = max(0.0, min(0.05, now - self.card_hover_last_at))
        self.card_hover_last_at = now
        for card_index, (card, (card_x, card_y)) in card_entries:
            elapsed = now - self.card_animation_started_at - card_index * CARD_ANIMATION_STAGGER
            progress = max(0.0, min(1.0, elapsed / CARD_ANIMATION_DURATION))
            eased = 1.0 - (1.0 - progress) ** 3
            spawn_scale = 0.08 + 0.92 * eased
            target_center_x = card_x + CARD_W / 2
            target_center_y = card_y + CARD_H / 2
            center_x = origin_x + (target_center_x - origin_x) * eased
            center_y = origin_y + (target_center_y - origin_y) * eased

            hover_progress = self.card_hover_progress.get(card_index, 0.0)
            if card_index == self.hovered_card_index:
                hover_progress = min(1.0, hover_progress + hover_delta / CARD_HOVER_DURATION)
            else:
                hover_progress = max(0.0, hover_progress - hover_delta / CARD_HOVER_DURATION)
            self.card_hover_progress[card_index] = hover_progress
            hover_eased = hover_progress * hover_progress * (3.0 - 2.0 * hover_progress)
            visual_scale = spawn_scale * (1.0 + CARD_HOVER_SCALE * hover_eased)
            center_y += CARD_HOVER_LIFT * hover_eased

            draw_w = max(2, round(CARD_W * visual_scale))
            draw_h = max(2, round(CARD_H * visual_scale))
            draw_x = round(center_x - draw_w / 2)
            draw_y = round(center_y - draw_h / 2)
            focused = card_index == self.action_cursor
            if focused:
                self._draw_card_rect(
                    center_x, center_y, draw_w, draw_h, GOLD, inset=-CARD_FOCUS_PADDING, filled=False
                )
            self._draw_card_rect(
                center_x, center_y, draw_w, draw_h, (31, 37, 50), inset=CARD_BACKGROUND_INSET
            )

            if progress >= 0.82:
                title_color = GOLD if focused else hero.accent
                visual_bottom = center_y - draw_h / 2
                self.text(
                    center_x,
                    visual_bottom + draw_h - 22 * visual_scale,
                    card.name,
                    max(10, round(14 * visual_scale)),
                    title_color,
                    centered=True,
                )
                description_lines = textwrap.wrap(card.description, width=9)[:2] or [card.description]
                description_start_y = visual_bottom + (58 if len(description_lines) > 1 else 51) * visual_scale
                for line_index, line in enumerate(description_lines):
                    self.text(
                        center_x,
                        description_start_y - line_index * 14 * visual_scale,
                        line,
                        max(9, round(11 * visual_scale)),
                        TEXT,
                        centered=True,
                    )
                self.text(
                    center_x,
                    visual_bottom + 20 * visual_scale,
                    f"×{card.power:.2f} · {card.short_effect()}",
                    max(9, round(10 * visual_scale)),
                    MINT if card.status_key else MUTED,
                    centered=True,
                )

            frame = self.card_frames[hero.unit_id]
            self.image(frame, center_x, center_y, draw_w, draw_h)

        rest = REST_RECT
        rest_focused = self.action_cursor == 5
        self.panel(
            rest[0],
            rest[1],
            rest[2] - rest[0],
            rest[3] - rest[1],
            (57, 50, 41) if rest_focused else PANEL_LIGHT,
            GOLD if rest_focused else LINE,
        )
        center_x = (rest[0] + rest[2]) / 2
        self.text(center_x, rest[1] + 113, "휴식", 18, GOLD if rest_focused else TEXT, centered=True)
        self.text(center_x, rest[1] + 77, "카드 보충", 12, MUTED, centered=True)

    def handle_mouse_move(self, battle: Battle, x: int, y: int) -> None:
        """Use pointer hover to focus cards or the nearest living enemy."""
        if battle.phase != "player" or not battle.active:
            self.hovered_card_index = None
            return
        self._sync_focus(battle)
        if battle.selected_card:
            self.hovered_card_index = None
            target = self._nearest_enemy(battle, x, y)
            if target:
                self.target_enemy_id = target.unit_id
            return
        card_positions = CARD_POSITIONS[:len(battle.active.hand[:5])]
        for index, (card_x, card_y) in enumerate(card_positions):
            if self._inside(x, y, self._card_pointer_rect(index, card_x, card_y, include_hover=False)):
                self.action_cursor = index
                self.hovered_card_index = index
                return

        previous_hover = self.hovered_card_index
        if previous_hover is not None and previous_hover < len(card_positions):
            card_x, card_y = card_positions[previous_hover]
            if self._inside(x, y, self._card_pointer_rect(previous_hover, card_x, card_y, include_hover=True)):
                self.action_cursor = previous_hover
                return

        self.hovered_card_index = None
        if self._inside(x, y, REST_RECT):
            self.action_cursor = 5

    def handle_mouse_click(self, battle: Battle, x: int, y: int) -> None:
        """Handle mouse selection, targeting, timing, and retry actions."""
        self._sync_focus(battle)
        if battle.phase in ("attack_timing", "defense_timing"):
            battle.submit_timing()
            return
        if battle.phase == "defeat":
            battle.reset()
            self.focus_actor_id = None
            self.focus_round = None
            return
        if battle.phase != "player" or not battle.active:
            return

        hero = battle.active
        if battle.selected_card:
            self.hovered_card_index = None
            if self._inside(x, y, CANCEL_TARGET_RECT):
                battle.cancel_card_selection(hero)
                return
            target = self._nearest_enemy(battle, x, y)
            if target and self._inside_enemy_area(battle, target, x, y):
                self.target_enemy_id = target.unit_id
                battle.begin_attack(hero, battle.selected_card, target)
            return
        if not self._card_animation_complete(battle):
            return

        for index, (card, (card_x, card_y)) in enumerate(zip(hero.hand[:5], CARD_POSITIONS)):
            card_rect = self._card_pointer_rect(
                index, card_x, card_y, include_hover=index == self.hovered_card_index
            )
            if self._inside(x, y, card_rect):
                self.action_cursor = index
                self.hovered_card_index = None
                battle.select_card(hero, card)
                target = self._nearest_enemy(battle, x, y)
                if target:
                    self.target_enemy_id = target.unit_id
                return
        if self._inside(x, y, REST_RECT):
            self.action_cursor = 5
            battle.rest(hero)
            self.action_cursor = 0

    def _card_animation_complete(self, battle: Battle, now: float | None = None) -> bool:
        card_count = min(len(battle.active.hand), len(CARD_POSITIONS)) if battle.active else 0
        if card_count <= 0:
            return True
        current = time.monotonic() if now is None else now
        last_card_start = self.card_animation_started_at + (card_count - 1) * CARD_ANIMATION_STAGGER
        return current >= last_card_start + CARD_ANIMATION_DURATION

    @staticmethod
    def _enemy_position(battle: Battle, enemy: Enemy) -> tuple[int, int]:
        index = battle.enemies.index(enemy)
        return ENEMY_POSITIONS[min(index, len(ENEMY_POSITIONS) - 1)]

    def _nearest_enemy(self, battle: Battle, x: int, y: int) -> Enemy | None:
        if not battle.living_enemies:
            return None
        return min(
            battle.living_enemies,
            key=lambda enemy: (
                (self._enemy_position(battle, enemy)[0] - x) ** 2
                + (self._enemy_position(battle, enemy)[1] - y) ** 2
            ),
        )

    def _inside_enemy_area(self, battle: Battle, enemy: Enemy, x: int, y: int) -> bool:
        enemy_x, enemy_y = self._enemy_position(battle, enemy)
        return abs(x - enemy_x) <= 110 and enemy_y - 180 <= y <= enemy_y + 85

    def _sync_focus(self, battle: Battle) -> None:
        if battle.active and (battle.active.unit_id != self.focus_actor_id or battle.round != self.focus_round):
            self.focus_actor_id = battle.active.unit_id
            self.focus_round = battle.round
            self.action_cursor = 0
            self.target_enemy_id = None
            self.card_animation_started_at = time.monotonic()
            self.hovered_card_index = None
            self.card_hover_progress.clear()
            self.card_hover_last_at = self.card_animation_started_at
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
        if key == p2d.SDLK_ESCAPE and battle.phase == "player" and battle.active and battle.selected_card:
            battle.cancel_card_selection(battle.active)
            return
        if battle.phase == "player" and battle.active and not battle.selected_card and not self._card_animation_complete(battle):
            return
        if key == p2d.SDLK_SPACE:
            if battle.phase in ("attack_timing", "defense_timing"):
                battle.submit_timing()
            elif battle.phase == "defeat":
                battle.reset()
                self.focus_actor_id = None
                self.focus_round = None
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

    def _card_pointer_rect(
        self, index: int, x: int, y: int, *, include_hover: bool
    ) -> tuple[float, float, float, float]:
        progress = max(0.0, min(1.0, self.card_hover_progress.get(index, 0.0)))
        eased = progress * progress * (3.0 - 2.0 * progress)
        scale = 1.0 + CARD_HOVER_SCALE * eased if include_hover else 1.0
        render_scale = min(SCALE_X, SCALE_Y)
        center_x = x + CARD_W / 2
        center_y = y + CARD_H / 2 + (CARD_HOVER_LIFT * eased if include_hover else 0.0)
        width = CARD_W * scale * render_scale / SCALE_X
        height = CARD_H * scale * render_scale / SCALE_Y
        return (
            center_x - width / 2,
            center_y - height / 2,
            center_x + width / 2,
            center_y + height / 2,
        )

    def _draw_card_rect(
        self,
        center_x: float,
        center_y: float,
        width: int,
        height: int,
        color: tuple[int, int, int],
        *,
        inset: int = 0,
        filled: bool = True,
    ) -> None:
        render_width = width - inset * 2
        render_height = height - inset * 2
        if render_width <= 0 or render_height <= 0:
            return
        render_scale = min(SCALE_X, SCALE_Y)
        logical_width = render_width * render_scale / SCALE_X
        logical_height = render_height * render_scale / SCALE_Y
        self.rect(
            round(center_x - logical_width / 2),
            round(center_y - logical_height / 2),
            round(logical_width),
            round(logical_height),
            color,
            filled=filled,
        )

    @staticmethod
    def _inside(x: int, y: int, rect: tuple[int, int, int, int]) -> bool:
        return rect[0] <= x <= rect[2] and rect[1] <= y <= rect[3]
