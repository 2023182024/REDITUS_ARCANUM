"""Pico2D rendering and mouse hit regions for the combat stage."""

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
GROUP_X = 24
GROUP_GAP = 8
GROUP_WIDTH = 342
GROUP_Y = 20
GROUP_HEIGHT = 252
CARD_W = 60
CARD_H = 108
CARD_GAP = 4

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
        self.card_rects: dict[tuple[str, int], tuple[int, int, int, int]] = {}
        self.rest_rects: dict[str, tuple[int, int, int, int]] = {}
        self.enemy_rects: dict[str, tuple[int, int, int, int]] = {}
        self.replay_rect = (0, 0, 0, 0)

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
        self.card_rects.clear()
        self.rest_rects.clear()
        self.enemy_rects.clear()
        p2d.clear_canvas()
        self.rect(0, 0, DESIGN_WIDTH, DESIGN_HEIGHT, INK)
        self._draw_header(battle)
        self._draw_order(battle)
        self._draw_battlefield(battle, now)
        self._draw_party_hands(battle)
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
        self.panel(28, 286, 1384, 492, (19, 25, 39), (54, 66, 86))
        self.text(48, 753, "BATTLE  /  잿빛 회랑", 16, MUTED)
        self.text(1085, 753, "TIMING COMMAND  ·  SPACE / CLICK", 13, GOLD)
        self.line(54, 393, 1385, 393, (44, 57, 77))
        self.line(54, 390, 1385, 390, (29, 38, 54))
        self.rect(47, 286, 1345, 74, (17, 22, 35))
        self.panel(48, 298, 1344, 44, (24, 31, 46), (45, 55, 72))
        if battle.log_lines:
            self.text(64, 320, "전투 기록", 13, GOLD)
            self.text(154, 320, battle.log_lines[0][:80], 14, TEXT)

        hero_x = (174, 348, 522, 696)
        for hero, x in zip(battle.party, hero_x):
            self._draw_hero(hero, x, battle)
        enemy_x = (1044, 1254)
        for enemy, x in zip(battle.enemies, enemy_x):
            self._draw_enemy(enemy, x, battle)

        if battle.phase in ("attack_timing", "defense_timing"):
            self._draw_timing(battle, now)
        elif battle.phase == "result":
            self._draw_result(battle)
        elif battle.phase == "victory":
            self._draw_end_card("전투 승리", "전투 스테이지 프로토타입을 완료했습니다.", True)
        elif battle.phase == "defeat":
            self._draw_end_card("전투 종료", "파티를 정비하고 다시 시도하세요.", False)
        elif battle.phase == "player" and battle.selected_card:
            card = battle.selected_card
            self.panel(464, 453, 510, 130, (27, 34, 50), GOLD)
            self.text(719, 554, f"선택한 스킬  ·  {card.name}", 22, GOLD, centered=True)
            self.text(719, 519, card.description, 16, TEXT, centered=True)
            self.text(719, 484, "공격할 적을 클릭하세요", 16, MUTED, centered=True)
        elif battle.phase == "player" and battle.active:
            self.panel(497, 468, 445, 100, (27, 34, 50), battle.active.accent)
            self.text(719, 535, f"{battle.active.name}  ·  ACTION", 21, battle.active.accent, centered=True)
            self.text(719, 501, "손패에서 카드를 고르거나 휴식하세요", 15, TEXT, centered=True)

    def _draw_hero(self, hero: PlayerCharacter, x: int, battle: Battle) -> None:
        active = hero is battle.active
        selected = active and battle.phase in ("attack_timing", "defense_timing", "result")
        border = GOLD if active else hero.accent
        glow = (34, 42, 57) if not active else (55, 51, 42)
        self.circle(x, 525, 91, glow, filled=True)
        if hero.alive:
            self.circle(x, 525, 92, border, filled=False)
            self.image(self.portraits[hero.unit_id], x, 535, 132, 198)
        else:
            self.circle(x, 525, 66, (70, 75, 86), filled=True)
            self.text(x, 528, "DOWN", 18, MUTED, centered=True)
        self.text(x, 410, hero.unit_id, 18, border, centered=True)
        if active and battle.phase == "player":
            self.text(x, 384, "NOW", 12, GOLD, centered=True)
        if hero.unit_id == "D" and hero.perfect_stacks:
            self.text(x, 445, f"PERFECT +{hero.perfect_stacks}", 12, GOLD, centered=True)
        if hero.statuses.snapshot():
            first = hero.statuses.snapshot()[0]
            self._draw_chip(x - 39, 363, first.label, (99, 58, 70))

    def _draw_enemy(self, enemy: Enemy, x: int, battle: Battle) -> None:
        target = enemy is battle.attack_target and battle.phase in ("attack_timing", "result")
        radius_color = GOLD if target else enemy.accent
        self.enemy_rects[enemy.unit_id] = (x - 80, 400, x + 80, 677)
        if not enemy.alive:
            self.circle(x, 535, 40, (72, 68, 81), filled=True)
            self.text(x, 535, "DOWN", 14, MUTED, centered=True)
        else:
            self.circle(x, 535, 65, radius_color, filled=False)
            self.circle(x, 535, 52, (46, 40, 63), filled=True)
            self.circle(x, 535, 36, enemy.accent, filled=True)
            self.circle(x, 535, 25, (31, 25, 45), filled=True)
            self.circle(x, 535, 14, (232, 203, 238), filled=True)
            for spoke in range(8):
                angle = spoke * 0.785398
                dx, dy = int(70 * __import__("math").cos(angle)), int(70 * __import__("math").sin(angle))
                self.line(x + dx, 535 + dy, x + int(dx * 1.22), 535 + int(dy * 1.22), enemy.accent)
        self.text(x, 687, enemy.name, 18, TEXT, centered=True)
        self._bar(x - 66, 660, 132, 9, enemy.hp / enemy.max_hp, CORAL)
        self.text(x, 637, f"HP  {enemy.hp}/{enemy.max_hp}   ·   ATK {enemy.attack}   SPD {enemy.speed}", 12, MUTED, centered=True)
        for i, effect in enumerate(enemy.statuses.snapshot()[:2]):
            self._draw_chip(x - 61 + i * 91, 610, effect.label, (110, 57, 68))

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
            self.text(720, 580, "정확한 순간에 SPACE 또는 클릭", 15, TEXT, centered=True)
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
        self.panel(635, 484, 170, 38, (61, 54, 43), GOLD)
        self.text(720, 503, "다시 전투", 16, GOLD, centered=True)
        self.replay_rect = (635, 484, 805, 522)
        self.text(720, 453, "보상 · 맵 이동 · 영입은 이 프로토타입 범위에 포함되지 않습니다.", 12, MUTED, centered=True)

    def _draw_party_hands(self, battle: Battle) -> None:
        for index, hero in enumerate(battle.party):
            x = GROUP_X + index * (GROUP_WIDTH + GROUP_GAP)
            is_active = hero is battle.active and battle.phase == "player"
            border = GOLD if is_active else LINE
            self.panel(x, GROUP_Y, GROUP_WIDTH, GROUP_HEIGHT, (30, 36, 51) if is_active else PANEL, border)
            self.text(x + 12, 247, f"{hero.name}", 16, hero.accent)
            self.text(x + 12, 224, f"HP {hero.hp}/{hero.max_hp}", 13, TEXT)
            self.text(x + 163, 224, f"ATK {hero.attack}  ·  SPD {hero.effective_speed()}", 12, MUTED)
            self._bar(x + 12, 207, GROUP_WIDTH - 24, 6, hero.hp / hero.max_hp, hero.accent)
            if hero.statuses.snapshot():
                status_text = "   ".join(effect.display() for effect in hero.statuses.snapshot()[:2])
                self.text(x + 12, 187, status_text[:30], 12, (218, 150, 145))
            else:
                self.text(x + 12, 187, hero.trait_text, 12, MUTED)
            self.text(x + 12, 170, f"손패 {len(hero.hand)}/5", 12, MUTED)

            for card_index, card in enumerate(hero.hand[:5]):
                card_x = x + 10 + card_index * (CARD_W + CARD_GAP)
                card_y = 56
                self.card_rects[(hero.unit_id, card_index)] = (card_x, card_y, card_x + CARD_W, card_y + CARD_H)
                selected = card is battle.selected_card
                available = is_active and battle.phase == "player"
                fill = (53, 48, 39) if selected else ((43, 50, 65) if available else (33, 38, 51))
                edge = GOLD if selected else (hero.accent if available else (61, 69, 84))
                self.panel(card_x, card_y, CARD_W, CARD_H, fill, edge)
                self.rect(card_x + 4, card_y + CARD_H - 5, CARD_W - 8, 3, hero.accent)
                title = card.name.replace(" ", "")
                self.text(card_x + CARD_W / 2, card_y + 84, title[:2], 12, TEXT if available else MUTED, centered=True)
                self.text(card_x + CARD_W / 2, card_y + 68, title[2:6], 12, TEXT if available else MUTED, centered=True)
                self.text(card_x + CARD_W / 2, card_y + 46, f"×{card.power:.2f}", 12, GOLD, centered=True)
                self.text(card_x + CARD_W / 2, card_y + 26, card.short_effect(), 12, MINT if card.status_key else MUTED, centered=True)
            rest = (x + GROUP_WIDTH - 82, 27, x + GROUP_WIDTH - 12, 50)
            self.rest_rects[hero.unit_id] = rest
            self.panel(rest[0], rest[1], rest[2] - rest[0], rest[3] - rest[1], (57, 50, 41) if is_active else PANEL_LIGHT, GOLD if is_active else LINE)
            self.text((rest[0] + rest[2]) / 2, 39, "휴식", 13, GOLD if is_active else MUTED, centered=True)
        self.text(30, 12, "카드 선택 → 적 클릭 → SPACE / 클릭  ·  휴식은 카드 보충", 12, MUTED)

    @staticmethod
    def _inside(x: int, y: int, rect: tuple[int, int, int, int]) -> bool:
        return rect[0] <= x <= rect[2] and rect[1] <= y <= rect[3]

    def handle_click(self, battle: Battle, x: int, y: int) -> None:
        if battle.phase in ("attack_timing", "defense_timing"):
            battle.submit_timing()
            return
        if battle.phase in ("victory", "defeat"):
            if self._inside(x, y, self.replay_rect):
                battle.reset()
            return
        if battle.phase != "player" or not battle.active:
            return
        hero = battle.active
        for (character_id, card_index), rect in self.card_rects.items():
            if character_id == hero.unit_id and self._inside(x, y, rect):
                battle.select_card(hero, hero.hand[card_index])
                return
        rest = self.rest_rects.get(hero.unit_id)
        if rest and self._inside(x, y, rest):
            battle.rest(hero)
            return
        if battle.selected_card:
            for enemy in battle.living_enemies:
                rect = self.enemy_rects.get(enemy.unit_id)
                if rect and self._inside(x, y, rect):
                    battle.begin_attack(hero, battle.selected_card, enemy)
                    return
            battle._note("공격할 적을 클릭하세요.")
