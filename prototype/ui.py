"""Pico2D rendering and mouse/keyboard controls for the combat stage."""

from __future__ import annotations

import math
import os
import time
import textwrap
from dataclasses import dataclass
from pathlib import Path

import pico2d as p2d

from battle import Battle
from cards import SkillCard
from units import Enemy, PlayerCharacter


DESIGN_WIDTH, DESIGN_HEIGHT = 1440, 960
WIDTH, HEIGHT = 1280, 720
SCALE_X = WIDTH / DESIGN_WIDTH
SCALE_Y = HEIGHT / DESIGN_HEIGHT
CARD_LAYOUT_SCALE = 1.266
CARD_W = round(140 * CARD_LAYOUT_SCALE)
CARD_H = round(188 * CARD_LAYOUT_SCALE)
HAND_OFFSET_X = 115
CARD_POSITIONS = tuple(
    (x + HAND_OFFSET_X, y)
    for x, y in ((410, 516), (625, 516), (410, 263), (625, 263), (410, 10))
)
REST_RECT = (625 + HAND_OFFSET_X, 10, 625 + HAND_OFFSET_X + CARD_W, 10 + CARD_H)
ENEMY_POSITIONS = ((1270, 585), (1270, 335))
PARTY_POSITIONS = ((360, 700), (360, 535), (360, 370), (360, 205))
WAITING_ALLY_POSITIONS = ((90, 700), (90, 510), (90, 320), (90, 130))
TURN_FOCUS_CENTER = (round(DESIGN_WIDTH / 4), DESIGN_HEIGHT // 2)
TURN_FOCUS_SCALE = 2.0
TURN_FOCUS_ANIMATION_DURATION = 0.38
CANCEL_TARGET_RECT = REST_RECT
CARD_ANIMATION_DURATION = 0.38
CARD_ANIMATION_STAGGER = 0.06
CARD_HAND_COLLAPSE_DURATION = 0.30
CARD_HOVER_DURATION = 0.16
CARD_HOVER_SCALE = 0.10
CARD_HOVER_LIFT = 17
CARD_BACKGROUND_INSET = 10
CARD_FOCUS_PADDING = 4
CARD_TARGET_CENTER = (720, 480)
CARD_TARGET_SCALE = 1.08

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


@dataclass
class CardMotion:
    hero_id: str
    card: SkillCard
    slot_index: int
    start_x: float
    start_y: float
    end_x: float
    end_y: float
    start_scale: float
    end_scale: float
    started_at: float


class BattleScreen:
    def __init__(self, asset_root: Path) -> None:
        self.asset_root = asset_root
        self.battle_background = p2d.load_image(
            str(asset_root / "images" / "backgrounds" / "floor1_battle_background.png")
        )
        self.target_arrow = p2d.load_image(str(asset_root / "images" / "ui" / "target_arrow.png"))
        self.font_file = self._find_font()
        self.fonts = {size: p2d.load_font(self.font_file, size) for size in (9, 10, 11, 12, 13, 14, 15, 16, 18, 20, 22, 24, 26, 28)}
        self.textures: dict[tuple[str, tuple[int, int, int], int], p2d.Image] = {}
        self.portraits: dict[str, p2d.Image] = {}
        self.small_portraits: dict[str, p2d.Image] = {}
        for character_id in "ABCD":
            path = asset_root / "images" / "characters_5x" / f"{character_id}.png"
            self.portraits[character_id] = p2d.load_image(str(path))
            small_path = asset_root / "images" / "characters_optimized" / f"{character_id}.png"
            self.small_portraits[character_id] = p2d.load_image(str(small_path))
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
        self.card_frames["enemy"] = p2d.load_image(
            str(asset_root / "images" / "card_frames" / "reditus_card_frame_enemy.png")
        )
        self.action_cursor = 0
        self.target_enemy_id: str | None = None
        self.focus_actor_id: str | None = None
        self.focus_round: int | None = None
        self.card_animation_started_at = 0.0
        self.card_hand_collapse_progress = 0.0
        self.card_hand_collapse_last_at = time.monotonic()
        self.hovered_card_index: int | None = None
        self.card_hover_progress: dict[int, float] = {}
        self.card_hover_last_at = time.monotonic()
        self.turn_focus_progress: dict[str, float] = {}
        self.turn_focus_last_at = time.monotonic()
        self.selected_card_key: tuple[str, int] | None = None
        self.selected_card_motion: CardMotion | None = None
        self.returning_card_motions: dict[tuple[str, int], CardMotion] = {}
        self.party_display_positions: dict[str, tuple[int, int]] = {}

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

    @staticmethod
    def image_flipped_horizontally(image: p2d.Image, x: int, y: int, w: int, h: int) -> None:
        scale = min(SCALE_X, SCALE_Y)
        image.composite_draw(
            0,
            "h",
            round(x * SCALE_X),
            round(y * SCALE_Y),
            round(w * scale),
            round(h * scale),
        )

    def panel(self, x: int, y: int, w: int, h: int, fill: tuple[int, int, int] = PANEL, border: tuple[int, int, int] = LINE) -> None:
        self.rect(x, y, w, h, fill)
        self.rect(x, y, w, h, border, filled=False)

    def draw(self, battle: Battle, now: float) -> None:
        self._sync_focus(battle)
        self._advance_turn_focus(battle, now)
        self._sync_selected_card_motion(battle, now)
        p2d.clear_canvas()
        self.battle_background.draw(WIDTH // 2, HEIGHT // 2, WIDTH, HEIGHT)
        self._draw_header(battle)
        self._draw_order(battle)
        self._draw_battlefield(battle, now)
        self._draw_action_cards(battle, now)
        if battle.phase == "player" and battle.selected_card:
            self._draw_selected_target_card(battle, now)
        self._draw_returning_card_motions(battle, now)
        p2d.update_canvas()

    def _draw_header(self, battle: Battle) -> None:
        self.text(30, 922, "REDITUS ARCANUM", 34, TEXT)
        self.text(1214, 925, f"TURN  {battle.round:02d}", 22, GOLD)
        self.text(1215, 894, "BATTLE STAGE  /  PROTOTYPE", 14, MUTED)

    def _draw_chip(self, x: int, y: int, title: str, fill: tuple[int, int, int]) -> None:
        self.panel(x, y - 13, 55, 26, fill, fill)
        self.text(x + 27, y, title, 14, TEXT, centered=True)

    def _advance_turn_focus(self, battle: Battle, now: float) -> None:
        elapsed = max(0.0, min(0.05, now - self.turn_focus_last_at))
        self.turn_focus_last_at = now
        progress_delta = elapsed / TURN_FOCUS_ANIMATION_DURATION
        for hero in battle.party:
            progress = self.turn_focus_progress.get(hero.unit_id, 0.0)
            if hero is battle.active:
                progress = min(1.0, progress + progress_delta)
            else:
                progress = max(0.0, progress - progress_delta)
            self.turn_focus_progress[hero.unit_id] = progress

    @staticmethod
    def _card_motion_value(motion: CardMotion, now: float) -> tuple[float, float, float, float]:
        progress = max(0.0, min(1.0, (now - motion.started_at) / CARD_ANIMATION_DURATION))
        eased = 1.0 - (1.0 - progress) ** 3
        center_x = motion.start_x + (motion.end_x - motion.start_x) * eased
        center_y = motion.start_y + (motion.end_y - motion.start_y) * eased
        scale = motion.start_scale + (motion.end_scale - motion.start_scale) * eased
        return center_x, center_y, scale, progress

    def _make_returning_motion(
        self, motion: CardMotion, now: float
    ) -> CardMotion:
        center_x, center_y, scale, _ = self._card_motion_value(motion, now)
        slot_x, slot_y = CARD_POSITIONS[motion.slot_index]
        return CardMotion(
            hero_id=motion.hero_id,
            card=motion.card,
            slot_index=motion.slot_index,
            start_x=center_x,
            start_y=center_y,
            end_x=slot_x + CARD_W / 2,
            end_y=slot_y + CARD_H / 2,
            start_scale=scale,
            end_scale=1.0,
            started_at=now,
        )

    def _sync_selected_card_motion(self, battle: Battle, now: float) -> None:
        self.returning_card_motions = {
            key: motion
            for key, motion in self.returning_card_motions.items()
            if now - motion.started_at < CARD_ANIMATION_DURATION
        }
        if battle.phase != "player":
            self.selected_card_key = None
            self.selected_card_motion = None
            self.returning_card_motions.clear()
            return

        hero = battle.active
        card = battle.selected_card
        selected_key = (hero.unit_id, id(card)) if hero and card else None
        if selected_key == self.selected_card_key:
            return

        if self.selected_card_key and self.selected_card_motion:
            old_key = self.selected_card_key
            self.returning_card_motions[old_key] = self._make_returning_motion(
                self.selected_card_motion, now
            )

        self.selected_card_key = selected_key
        self.selected_card_motion = None
        if not hero or not card or card not in hero.hand:
            return

        slot_index = hero.hand.index(card)
        slot_x, slot_y = CARD_POSITIONS[slot_index]
        returning_motion = self.returning_card_motions.pop(selected_key, None)
        if returning_motion:
            start_x, start_y, start_scale, _ = self._card_motion_value(returning_motion, now)
        else:
            hover_progress = self.card_hover_progress.get(slot_index, 0.0)
            hover_eased = hover_progress * hover_progress * (3.0 - 2.0 * hover_progress)
            start_x = slot_x + CARD_W / 2
            start_y = slot_y + CARD_H / 2 + CARD_HOVER_LIFT * hover_eased
            start_scale = 1.0 + CARD_HOVER_SCALE * hover_eased
        target_x, target_y = CARD_TARGET_CENTER
        self.selected_card_motion = CardMotion(
            hero_id=hero.unit_id,
            card=card,
            slot_index=slot_index,
            start_x=start_x,
            start_y=start_y,
            end_x=target_x,
            end_y=target_y,
            start_scale=start_scale,
            end_scale=CARD_TARGET_SCALE,
            started_at=now,
        )

    @staticmethod
    def _card_power_label(card: SkillCard) -> str:
        count = f"{card.hit_count}회" if card.hit_count > 1 else "홀드" if card.hold_to_judge else "1회"
        return f"×{card.power:.2f} · {count} · {card.short_effect()}"

    def _draw_skill_card_face(
        self,
        hero: PlayerCharacter,
        card: SkillCard,
        center_x: float,
        center_y: float,
        visual_scale: float,
    ) -> None:
        draw_w = max(2, round(CARD_W * visual_scale))
        draw_h = max(2, round(CARD_H * visual_scale))
        self._draw_card_rect(
            center_x,
            center_y,
            draw_w,
            draw_h,
            (31, 37, 50),
            inset=round(CARD_BACKGROUND_INSET * visual_scale),
        )
        content_scale = visual_scale * CARD_LAYOUT_SCALE
        visual_bottom = center_y - draw_h / 2
        self.text(
            center_x,
            visual_bottom + draw_h - 22 * content_scale,
            card.name,
            max(10, round(14 * content_scale)),
            hero.accent,
            centered=True,
        )
        description_lines = textwrap.wrap(card.description, width=9)[:2] or [card.description]
        description_start_y = visual_bottom + (58 if len(description_lines) > 1 else 51) * content_scale
        for line_index, line in enumerate(description_lines):
            self.text(
                center_x,
                description_start_y - line_index * 14 * content_scale,
                line,
                max(9, round(11 * content_scale)),
                TEXT,
                centered=True,
            )
        self.text(
            center_x,
            visual_bottom + 20 * content_scale,
            self._card_power_label(card),
            max(9, round(10 * content_scale)),
            MINT if card.status_key or card.effect_key else MUTED,
            centered=True,
        )
        self.image(self.card_frames[hero.unit_id], center_x, center_y, draw_w, draw_h)

    def _draw_returning_card_motions(self, battle: Battle, now: float) -> None:
        heroes = {hero.unit_id: hero for hero in battle.party}
        for motion in self.returning_card_motions.values():
            hero = heroes.get(motion.hero_id)
            if not hero:
                continue
            center_x, center_y, visual_scale, _ = self._card_motion_value(motion, now)
            self._draw_skill_card_face(hero, motion.card, center_x, center_y, visual_scale)

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
            label = actor.name.split(" · ", 1)[0] if actor.side == "player" else actor.name[:4]
            self.text(x + 11, 832, label, 14, color)
            self.text(x + 11, 813, f"SPD {actor.effective_speed()}", 12, MUTED)
            self.text(x + 133, 825, f"d{entry.die}", 12, GOLD if active else MUTED, centered=True)
            if not actor.alive:
                self.rect(x + 1, 805, 162, 43, INK)
                self.text(x + 82, 825, "DOWN", 12, MUTED, centered=True)

    def _draw_battlefield(self, battle: Battle, now: float) -> None:
        self.rect(28, 0, 1384, 778, (54, 66, 86), filled=False)
        self.text(48, 753, "전투", 16, MUTED)
        self.line(270, 187, 1170, 187, (44, 57, 77))

        self.party_display_positions = self._party_display_positions(battle)
        for hero in battle.party:
            hero_x, hero_y = self.party_display_positions[hero.unit_id]
            self._draw_hero(hero, hero_x, hero_y, battle)
        for enemy, (enemy_x, enemy_y) in zip(battle.enemies, ENEMY_POSITIONS):
            self._draw_enemy(enemy, enemy_x, enemy_y, battle)
        if battle.active:
            active_hero = next(
                (hero for hero in battle.party if hero.unit_id == battle.active.unit_id),
                None,
            )
            if active_hero and self.turn_focus_progress.get(active_hero.unit_id, 0.0) >= 0.82:
                self._draw_active_hero_stats(active_hero, battle)
        self._draw_attack_effect(battle, now)

        if battle.phase == "enemy_skill_reveal":
            self._draw_enemy_skill_reveal(battle, now)
            self._draw_incoming_target_arrow(battle)
        elif battle.phase in ("attack_timing", "defense_timing", "hold_wait", "hold_timing", "multi_hit_pause"):
            self._draw_timing(battle, now)
            if battle.phase == "defense_timing":
                self._draw_incoming_target_arrow(battle)
        elif battle.phase == "result":
            self._draw_result(battle, now)
        elif battle.phase == "victory":
            self._draw_end_card("전투 승리", "1층 맵으로 돌아갑니다.", True)
        elif battle.phase == "defeat":
            self._draw_end_card("전투 종료", "파티를 정비하고 다시 시도하세요.", False)
        elif battle.phase == "player" and battle.selected_card:
            target = self._focused_enemy(battle)
            if target:
                _, target_y = self._enemy_position(battle, target)
                self._draw_target_arrow(1170, target_y)

    def _draw_selected_target_card(self, battle: Battle, now: float) -> None:
        hero = battle.active
        card = battle.selected_card
        motion = self.selected_card_motion
        if not hero or not card:
            return
        if motion and motion.card is card and motion.hero_id == hero.unit_id:
            center_x, center_y, visual_scale, _ = self._card_motion_value(motion, now)
        else:
            center_x, center_y = CARD_TARGET_CENTER
            visual_scale = CARD_TARGET_SCALE
        self._draw_skill_card_face(hero, card, center_x, center_y, visual_scale)

    def _draw_hero(self, hero: PlayerCharacter, x: int, y: int, battle: Battle) -> None:
        active = hero is battle.active
        border = GOLD if active else hero.accent
        glow = (34, 42, 57) if not active else (55, 51, 42)
        display_x, display_y, visual_scale = self._hero_visual_position(hero, x, y)
        portrait_width, portrait_height = (110, 165) if active else (100, 150)
        portrait_scale = visual_scale if active else min(1.0, visual_scale)
        radius = round((60 if active else 50) * portrait_scale)
        self.circle(display_x, display_y, radius, glow, filled=True)
        if hero.alive:
            self.circle(display_x, display_y, radius, border, filled=False)
            self.image(
                self.portraits[hero.unit_id] if active else self.small_portraits[hero.unit_id],
                display_x,
                display_y,
                round(portrait_width * portrait_scale),
                round(portrait_height * portrait_scale),
            )
        else:
            self.circle(display_x, display_y, 30 if active else 22, (70, 75, 86), filled=True)
            self.text(display_x, display_y, "DOWN", 14, MUTED, centered=True)
        if not active:
            info_x = display_x + 105
            short_name = hero.name.split(" · ", 1)[0]
            self.text(info_x, display_y + 52, short_name, 12, border, centered=True)
            self._bar(info_x - 58, display_y + 32, 116, 5, hero.hp / hero.max_hp, hero.accent)
            self.text(
                info_x,
                display_y + 12,
                f"HP {hero.hp}/{hero.max_hp}",
                9,
                MUTED,
                centered=True,
            )
            self.text(
                info_x,
                display_y - 7,
                f"ATK {hero.attack} · SPD {hero.effective_speed()}",
                9,
                MUTED,
                centered=True,
            )
            effects = hero.statuses.snapshot()[:1]
            for index, effect in enumerate(effects):
                self.text(info_x, display_y - 27, effect.display(), 9, CORAL, centered=True)
            if hero.unit_id == "D" and hero.perfect_stacks:
                self.text(info_x, display_y - 44, f"P+{hero.perfect_stacks}", 9, GOLD, centered=True)

    def _party_display_positions(self, battle: Battle) -> dict[str, tuple[int, int]]:
        if battle.active and battle.active.side == "player":
            active_index = battle.party.index(battle.active)
            positions = {
                battle.active.unit_id: PARTY_POSITIONS[min(active_index, len(PARTY_POSITIONS) - 1)]
            }
            inactive_slots = iter(WAITING_ALLY_POSITIONS)
            for hero in battle.party:
                if hero is not battle.active:
                    positions[hero.unit_id] = next(inactive_slots)
            return positions

        return {
            hero.unit_id: WAITING_ALLY_POSITIONS[min(index, len(WAITING_ALLY_POSITIONS) - 1)]
            for index, hero in enumerate(battle.party)
        }

    def _hero_visual_position(
        self, hero: PlayerCharacter, x: int, y: int
    ) -> tuple[int, int, float]:
        focus_progress = self.turn_focus_progress.get(hero.unit_id, 0.0)
        focus_eased = focus_progress * focus_progress * (3.0 - 2.0 * focus_progress)
        focus_x, focus_y = TURN_FOCUS_CENTER
        display_x = round(x + (focus_x - x) * focus_eased)
        display_y = round(y + (focus_y - y) * focus_eased)
        visual_scale = 1.0 + (TURN_FOCUS_SCALE - 1.0) * focus_eased
        return display_x, display_y, visual_scale

    def _draw_active_hero_stats(self, hero: PlayerCharacter, battle: Battle) -> None:
        hero_index = battle.party.index(hero)
        base_x, base_y = PARTY_POSITIONS[min(hero_index, len(PARTY_POSITIONS) - 1)]
        display_x, display_y, visual_scale = self._hero_visual_position(hero, base_x, base_y)
        portrait_bottom = display_y - 82.5 * visual_scale
        panel_top = round(portrait_bottom - 12)
        panel_height = 116
        panel_width = 300
        left = display_x - panel_width // 2
        bottom = panel_top - panel_height
        self.panel(left, bottom, panel_width, panel_height, (18, 24, 37), hero.accent)
        self.text(display_x, panel_top - 20, hero.name, 17, hero.accent, centered=True)
        self._bar(left + 40, panel_top - 45, panel_width - 80, 8, hero.hp / hero.max_hp, hero.accent)
        self.text(display_x, panel_top - 61, f"HP  {hero.hp} / {hero.max_hp}", 14, TEXT, centered=True)
        self.text(
            display_x,
            panel_top - 82,
            f"공격력  {hero.attack}     속도  {hero.effective_speed()}",
            14,
            MUTED,
            centered=True,
        )
        effects = hero.statuses.snapshot()[:1]
        if effects:
            self._draw_chip(left + panel_width - 120, bottom + 14, effects[0].label, (99, 58, 70))
        if hero.unit_id == "D" and hero.perfect_stacks:
            self._draw_chip(left + panel_width - 60, bottom + 14, f"P+{hero.perfect_stacks}", (99, 81, 43))

    def _draw_incoming_target_arrow(self, battle: Battle) -> None:
        target = battle.incoming_target
        if not target:
            return
        hero_x, hero_y = self.party_display_positions.get(
            target.unit_id,
            PARTY_POSITIONS[min(battle.party.index(target), len(PARTY_POSITIONS) - 1)],
        )
        display_x, display_y, visual_scale = self._hero_visual_position(target, hero_x, hero_y)
        arrow_center_x = round(display_x + 55 * visual_scale + 96)
        self.image_flipped_horizontally(self.target_arrow, arrow_center_x, display_y, 120, 108)

    def _draw_enemy(self, enemy: Enemy, x: int, y: int, battle: Battle) -> None:
        selected_target = enemy.unit_id == self.target_enemy_id and battle.phase == "player" and battle.selected_card
        target = selected_target or (
            enemy is battle.attack_target
            and battle.phase in ("attack_timing", "hold_wait", "hold_timing", "multi_hit_pause", "result")
        )
        target = target or (enemy is battle.incoming_source and battle.phase == "enemy_skill_reveal")
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

    def _unit_position(self, battle: Battle, unit) -> tuple[int, int]:
        if unit.side == "player":
            base_x, base_y = self.party_display_positions.get(
                unit.unit_id,
                PARTY_POSITIONS[min(battle.party.index(unit), len(PARTY_POSITIONS) - 1)],
            )
            display_x, display_y, _ = self._hero_visual_position(unit, base_x, base_y)
            return display_x, display_y
        index = battle.enemies.index(unit)
        return ENEMY_POSITIONS[min(index, len(ENEMY_POSITIONS) - 1)]

    def _bar(self, x: int, y: int, w: int, h: int, ratio: float, color: tuple[int, int, int]) -> None:
        self.rect(x, y, w, h, (43, 49, 62))
        self.rect(x, y, int(w * max(0, min(1, ratio))), h, color)

    def _draw_enemy_skill_reveal(self, battle: Battle, now: float) -> None:
        source = battle.incoming_source
        skill = battle.incoming_skill
        if not source or not skill:
            return

        target_x, target_y = 720, 470
        target_bottom = target_y - CARD_H / 2
        self.text(target_x, target_bottom + CARD_H + 34, f"{source.name} · 적 스킬", 14, CORAL, centered=True)

        source_x, source_y = self._unit_position(battle, source)
        progress = max(
            0.0,
            min(1.0, (now - battle.enemy_skill_reveal_started_at) / CARD_ANIMATION_DURATION),
        )
        eased = 1.0 - (1.0 - progress) ** 3
        visual_scale = 0.08 + 0.92 * eased
        center_x = source_x + (target_x - source_x) * eased
        center_y = source_y + (target_y - source_y) * eased
        draw_w = max(2, round(CARD_W * visual_scale))
        draw_h = max(2, round(CARD_H * visual_scale))
        content_scale = visual_scale * CARD_LAYOUT_SCALE
        self._draw_card_rect(
            center_x,
            center_y,
            draw_w,
            draw_h,
            (31, 37, 50),
            inset=round(CARD_BACKGROUND_INSET * visual_scale),
        )

        if progress >= 0.82:
            visual_bottom = center_y - draw_h / 2
            self.text(
                center_x,
                visual_bottom + draw_h - 22 * content_scale,
                skill.name,
                max(10, round(14 * content_scale)),
                source.accent,
                centered=True,
            )
            description_lines = textwrap.wrap(skill.description, width=9)[:2] or [skill.description]
            description_start_y = visual_bottom + (58 if len(description_lines) > 1 else 51) * content_scale
            for line_index, line in enumerate(description_lines):
                self.text(
                    center_x,
                    description_start_y - line_index * 14 * content_scale,
                    line,
                    max(9, round(11 * content_scale)),
                    TEXT,
                    centered=True,
                )
            self.text(
                center_x,
                visual_bottom + 20 * content_scale,
                f"×{skill.power:.2f} · {skill.short_effect()}",
                max(9, round(10 * content_scale)),
                MINT if skill.status_key else MUTED,
                centered=True,
            )

        self.image(self.card_frames["enemy"], center_x, center_y, draw_w, draw_h)

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
            if battle.phase == "hold_wait":
                prompt = "SPACE를 누른 뒤, 타이밍에 맞춰 놓으세요"
            elif battle.phase == "hold_timing":
                prompt = "SPACE를 놓으면 판정됩니다"
            elif battle.phase == "multi_hit_pause":
                prompt = f"다음 타격 준비 · {battle.attack_hit_index + 1}/{card.hit_count}"
            elif card and card.hit_count > 1:
                prompt = f"타격 {battle.attack_hit_index + 1}/{card.hit_count} · SPACE로 판정"
            else:
                prompt = "정확한 순간에 SPACE"
            self.text(720, 580, prompt, 15, TEXT, centered=True)
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

    def _draw_result(self, battle: Battle, now: float) -> None:
        elapsed = max(0.0, now - battle.result_started_at)
        pop = min(1.0, elapsed / 0.16)
        scale = 0.78 + 0.22 * (1.0 - (1.0 - pop) ** 3)
        opacity = max(0.0, 1.0 - max(0.0, (elapsed - 0.58) / 0.32))

        result_image = self._text_image(battle.result_quality, battle.result_color, 64)
        result_image.opacify(opacity)
        result_image.draw(
            round(720 * SCALE_X),
            round(480 * SCALE_Y),
            round(result_image.w * scale),
            round(result_image.h * scale),
        )
        result_image.opacify(1.0)

        units = (*battle.party, *battle.enemies)
        target = next(
            (unit for unit in units if unit.unit_id == battle.result_target_id),
            None,
        )
        if target:
            x, y = self._unit_position(battle, target)
            number_image = self._text_image(
                "0" if battle.result_damage == 0 else f"-{battle.result_damage}",
                battle.result_color,
                30,
            )
            number_image.opacify(opacity)
            number_image.draw(
                round(x * SCALE_X),
                round((y + 76 + min(38, elapsed * 45)) * SCALE_Y),
                number_image.w,
                number_image.h,
            )
            number_image.opacify(1.0)

    def _draw_end_card(self, title: str, message: str, victory: bool) -> None:
        border = GOLD if victory else CORAL
        self.panel(472, 462, 496, 174, (26, 32, 47), border)
        self.text(720, 585, title, 30, border, centered=True)
        self.text(720, 548, message, 16, TEXT, centered=True)
        if not victory:
            self.text(720, 503, "SPACE · 다시 전투", 16, GOLD, centered=True)

    def _draw_target_arrow(self, tip_x: int, y: int) -> None:
        """Show the outlined arrow image that marks the selected enemy."""
        self.image(self.target_arrow, tip_x - 51, y, 120, 108)

    def _draw_action_cards(self, battle: Battle, now: float) -> None:
        """Draw portrait skill cards and smoothly enlarge the card under the pointer."""
        if battle.phase != "player" or not battle.active:
            return
        hero = battle.active
        selecting_target = battle.selected_card is not None
        action_indices = list(range(min(len(hero.hand), 5))) + [5]
        if self.action_cursor not in action_indices:
            self.action_cursor = action_indices[0]
        hand_center_x = (CARD_POSITIONS[0][0] + REST_RECT[2]) / 2
        prompt = "공격할 적을 선택하세요" if selecting_target else "사용할 스킬을 선택하세요"
        self.text(hand_center_x, 773, f"{hero.name} · {prompt}", 14, hero.accent, centered=True)
        hero_index = battle.party.index(hero)
        hero_x, hero_y = PARTY_POSITIONS[min(hero_index, len(PARTY_POSITIONS) - 1)]
        focus_progress = self.turn_focus_progress.get(hero.unit_id, 0.0)
        focus_eased = focus_progress * focus_progress * (3.0 - 2.0 * focus_progress)
        focus_x, focus_y = TURN_FOCUS_CENTER
        origin_x = round(hero_x + (focus_x - hero_x) * focus_eased)
        origin_y = round(hero_y + (focus_y - hero_y) * focus_eased)
        returning_keys = {
            key for key, motion in self.returning_card_motions.items() if motion.hero_id == hero.unit_id
        }
        collapse_delta = max(0.0, min(0.05, now - self.card_hand_collapse_last_at))
        self.card_hand_collapse_last_at = now
        if selecting_target:
            self.card_hand_collapse_progress = min(
                1.0, self.card_hand_collapse_progress + collapse_delta / CARD_HAND_COLLAPSE_DURATION
            )
        else:
            self.card_hand_collapse_progress = max(
                0.0, self.card_hand_collapse_progress - collapse_delta / CARD_HAND_COLLAPSE_DURATION
            )
        collapse_progress = self.card_hand_collapse_progress
        collapse_eased = collapse_progress * collapse_progress * (3.0 - 2.0 * collapse_progress)
        card_entries = [
            (index, (card, CARD_POSITIONS[index]))
            for index, card in enumerate(hero.hand[:5])
            if card is not battle.selected_card and (hero.unit_id, id(card)) not in returning_keys
        ]
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
            center_x += (origin_x - center_x) * collapse_eased
            center_y += (origin_y - center_y) * collapse_eased
            visual_scale *= 1.0 - collapse_eased
            if visual_scale <= 0.025:
                continue

            draw_w = max(2, round(CARD_W * visual_scale))
            draw_h = max(2, round(CARD_H * visual_scale))
            content_scale = visual_scale * CARD_LAYOUT_SCALE
            focused = card_index == self.action_cursor
            if focused:
                self._draw_card_rect(
                    center_x, center_y, draw_w, draw_h, GOLD, inset=-CARD_FOCUS_PADDING, filled=False
                )
            self._draw_card_rect(
                center_x, center_y, draw_w, draw_h, (31, 37, 50), inset=CARD_BACKGROUND_INSET
            )

            if progress >= 0.82 and visual_scale >= 0.65:
                title_color = GOLD if focused else hero.accent
                visual_bottom = center_y - draw_h / 2
                self.text(
                    center_x,
                    visual_bottom + draw_h - 22 * content_scale,
                    card.name,
                    max(10, round(14 * content_scale)),
                    title_color,
                    centered=True,
                )
                description_lines = textwrap.wrap(card.description, width=9)[:2] or [card.description]
                description_start_y = visual_bottom + (58 if len(description_lines) > 1 else 51) * content_scale
                for line_index, line in enumerate(description_lines):
                    self.text(
                        center_x,
                        description_start_y - line_index * 14 * content_scale,
                        line,
                        max(9, round(11 * content_scale)),
                        TEXT,
                        centered=True,
                    )
                self.text(
                    center_x,
                    visual_bottom + 20 * content_scale,
                    self._card_power_label(card),
                    max(9, round(10 * content_scale)),
                    MINT if card.status_key or card.effect_key else MUTED,
                    centered=True,
                )

            frame = self.card_frames[hero.unit_id]
            self.image(frame, center_x, center_y, draw_w, draw_h)

        rest = REST_RECT
        center_x = (rest[0] + rest[2]) / 2
        center_y = (rest[1] + rest[3]) / 2
        if selecting_target:
            self._draw_card_rect(center_x, center_y, CARD_W, CARD_H, (57, 50, 41))
            self._draw_card_rect(center_x, center_y, CARD_W, CARD_H, GOLD, filled=False)
            self.text(center_x, rest[1] + 113 * CARD_LAYOUT_SCALE, "취소", round(18 * CARD_LAYOUT_SCALE), GOLD, centered=True)
            self.text(center_x, rest[1] + 77 * CARD_LAYOUT_SCALE, "카드 선택으로", round(12 * CARD_LAYOUT_SCALE), MUTED, centered=True)
        else:
            rest_focused = self.action_cursor == 5
            rest_fill = (57, 50, 41) if rest_focused else PANEL_LIGHT
            rest_border = GOLD if rest_focused else LINE
            self._draw_card_rect(center_x, center_y, CARD_W, CARD_H, rest_fill)
            self._draw_card_rect(center_x, center_y, CARD_W, CARD_H, rest_border, filled=False)
            self.text(center_x, rest[1] + 113 * CARD_LAYOUT_SCALE, "휴식", round(18 * CARD_LAYOUT_SCALE), GOLD if rest_focused else TEXT, centered=True)
            self.text(center_x, rest[1] + 77 * CARD_LAYOUT_SCALE, "카드 보충", round(12 * CARD_LAYOUT_SCALE), MUTED, centered=True)

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
        for index, (card, (card_x, card_y)) in enumerate(zip(battle.active.hand[:5], CARD_POSITIONS)):
            if (battle.active.unit_id, id(card)) in self.returning_card_motions:
                continue
            if self._inside(x, y, self._card_pointer_rect(index, card_x, card_y, include_hover=False)):
                self.action_cursor = index
                self.hovered_card_index = index
                return

        previous_hover = self.hovered_card_index
        if previous_hover is not None and previous_hover < len(CARD_POSITIONS):
            card_x, card_y = CARD_POSITIONS[previous_hover]
            if self._inside(x, y, self._card_pointer_rect(previous_hover, card_x, card_y, include_hover=True)):
                self.action_cursor = previous_hover
                return

        self.hovered_card_index = None
        if self._inside(x, y, REST_RECT):
            self.action_cursor = 5

    def handle_mouse_click(self, battle: Battle, x: int, y: int) -> None:
        """Handle mouse selection, targeting, and retry actions."""
        self._sync_focus(battle)
        if battle.phase in ("attack_timing", "defense_timing", "hold_wait", "hold_timing", "multi_hit_pause"):
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
            if (hero.unit_id, id(card)) in self.returning_card_motions:
                continue
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
            self.returning_card_motions.clear()
            self.focus_actor_id = battle.active.unit_id
            self.focus_round = battle.round
            self.action_cursor = 0
            self.target_enemy_id = None
            self.card_animation_started_at = time.monotonic()
            self.card_hand_collapse_progress = 0.0
            self.card_hand_collapse_last_at = self.card_animation_started_at
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
            if battle.phase == "hold_wait":
                battle.start_hold_timing()
            elif battle.phase in ("attack_timing", "defense_timing"):
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

    def handle_key_up(self, battle: Battle, key: int) -> None:
        if key == p2d.SDLK_SPACE:
            battle.release_hold_timing()

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
