"""Turn order, card play, timing commands and battle resolution."""

from __future__ import annotations

import random
import time
from dataclasses import dataclass

from cards import SkillCard
from units import Combatant, Enemy, PlayerCharacter, create_enemies, create_party


@dataclass
class TurnEntry:
    actor: Combatant
    die: int


class Battle:
    PERFECT_MULTIPLIER = 1.6
    GOOD_MULTIPLIER = 1.0
    MISS_MULTIPLIER = 0.5

    def __init__(self, character_ids: list[str] | None = None, encounter_id: str = "corridor") -> None:
        self.character_ids = list(character_ids) if character_ids is not None else list("ABCD")
        self.encounter_id = encounter_id
        self.party = create_party(self.character_ids)
        self.enemies = create_enemies(encounter_id)
        self.round = 1
        self.order: list[TurnEntry] = []
        self.order_index = 0
        self.phase = "player"
        self.active: PlayerCharacter | None = None
        self.selected_card: SkillCard | None = None
        self.attack_target: Enemy | None = None
        self.incoming_target: PlayerCharacter | None = None
        self.incoming_source: Enemy | None = None
        self.incoming_skill: SkillCard | None = None
        self.timing_start = time.monotonic()
        self.timing_speed = 1.0
        self.timing_center = 0.5
        self.perfect_window = 0.055
        self.good_window = 0.17
        self.timing_bonus = 0.0
        self.result_text = ""
        self.result_color = (240, 236, 218)
        self.result_until = 0.0
        self.log_lines: list[str] = []
        self.roll_by_id: dict[str, int] = {}
        self.rng = random.Random()
        self._build_order()
        self._note("전투 시작 · 캐릭터별 덱에서 손패 3장을 뽑았습니다.")
        self._prepare_actor()

    @property
    def living_enemies(self) -> list[Enemy]:
        return [enemy for enemy in self.enemies if enemy.alive]

    @property
    def living_party(self) -> list[PlayerCharacter]:
        return [hero for hero in self.party if hero.alive]

    def _note(self, message: str) -> None:
        self.log_lines.insert(0, message)
        self.log_lines = self.log_lines[:4]

    def _build_order(self) -> None:
        actors = [unit for unit in (*self.party, *self.enemies) if unit.alive]
        self.roll_by_id = {unit.unit_id: self.rng.randint(1, 6) for unit in actors}
        actors.sort(key=lambda unit: (-unit.effective_speed(), -self.roll_by_id[unit.unit_id]))
        self.order = [TurnEntry(unit, self.roll_by_id[unit.unit_id]) for unit in actors]
        self.order_index = 0

    def _check_battle_end(self) -> bool:
        if not self.living_enemies:
            self.phase = "victory"
            self.active = None
            self._note("전투 승리 · 전투 화면 범위가 종료되었습니다.")
            return True
        if not self.living_party:
            self.phase = "defeat"
            self.active = None
            self._note("파티 전원이 전투 불능입니다.")
            return True
        return False

    def _prepare_actor(self) -> None:
        if self._check_battle_end():
            return
        while True:
            if self.order_index >= len(self.order):
                self._end_round()
                if self._check_battle_end():
                    return
                self.round += 1
                self._build_order()
                self._note(f"{self.round}턴 시작 · 속도 순서가 정해졌습니다.")
            entry = self.order[self.order_index]
            actor = entry.actor
            if not actor.alive:
                self.order_index += 1
                continue
            if actor.statuses.has("stun"):
                actor.statuses.consume("stun")
                self._note(f"{actor.name} · 기절로 행동을 건너뜁니다.")
                self.order_index += 1
                continue
            if isinstance(actor, PlayerCharacter):
                self.active = actor
                self.phase = "player"
                self.selected_card = None
                self._note(f"{actor.name}의 차례입니다. 카드를 고르거나 휴식하세요.")
                return
            if self.rng.random() < 0.12:
                self._note(f"{actor.name} · 전열을 살피며 행동을 멈췄습니다.")
                self.order_index += 1
                continue
            self._enemy_action(actor)
            if self.phase == "defense_timing":
                return

    def _end_round(self) -> None:
        for unit in (*self.party, *self.enemies):
            if not unit.alive:
                continue
            bleed_damage, removed = unit.statuses.end_round()
            if bleed_damage:
                unit.hp = max(0, unit.hp - bleed_damage)
                unit.alive = unit.hp > 0
                self._note(f"{unit.name} · 출혈 피해 {bleed_damage}.")
            for key in removed:
                label = {"bleed": "출혈", "slow": "둔화", "rest_lock": "강박"}[key]
                self._note(f"{unit.name} · {label} 효과가 해제되었습니다.")
        for hero in self.party:
            hero.rested = False

    def _enemy_action(self, enemy: Enemy) -> None:
        # Resting heroes are less likely to be selected as an enemy's target.
        rested = [hero for hero in self.living_party if hero.rested]
        active_targets = [hero for hero in self.living_party if not hero.rested]
        if rested and active_targets and self.rng.random() < 0.72:
            target = self.rng.choice(active_targets)
        else:
            target = self.rng.choice(self.living_party)
        skill = enemy.choose_skill()
        self.incoming_source = enemy
        self.incoming_target = target
        self.incoming_skill = skill
        self.timing_start = time.monotonic()
        self.timing_speed = skill.timing_speed
        self.timing_center = 0.5
        bonus = 0.04 if target.unit_id == "A" else 0
        self.timing_bonus = bonus
        self.perfect_window = 0.055 + bonus
        self.good_window = 0.17 + bonus
        self.phase = "defense_timing"
        self.active = None
        self._note(f"{enemy.name} · {skill.name}! {target.name}가 방어 커맨드를 입력합니다.")

    def begin_attack(self, hero: PlayerCharacter, card: SkillCard, target: Enemy) -> None:
        if self.phase != "player" or hero is not self.active:
            return
        if card not in hero.hand or not target.alive:
            return
        hero.hand.remove(card)
        self.selected_card = card
        self.attack_target = target
        self.timing_start = time.monotonic()
        self.timing_speed = card.timing_speed
        self.timing_center = 0.5
        bonus = 0.045 if hero.unit_id == "A" else 0
        self.perfect_window = card.perfect_window + bonus
        self.good_window = card.good_window + bonus
        self.timing_bonus = bonus
        self.phase = "attack_timing"
        self._note(f"{hero.name} · {card.name} · SPACE로 타이밍 입력")

    def select_card(self, hero: PlayerCharacter, card: SkillCard) -> None:
        if self.phase != "player" or hero is not self.active or card not in hero.hand:
            return
        self.selected_card = card
        self._note(f"선택 · {card.name} · 적을 클릭해 대상을 정하세요.")

    def rest(self, hero: PlayerCharacter) -> None:
        if self.phase != "player" or hero is not self.active:
            return
        if hero.hand and self._is_rest_locked(hero):
            self._note(f"{hero.name} · 강박 상태라 휴식할 수 없습니다.")
            return
        # An empty hand forces a rest and clears the lock.
        if self._is_rest_locked(hero) and not hero.hand:
            hero.statuses.consume("rest_lock")
        amount = 2 if hero.unit_id == "C" else 1
        drawn = hero.draw(amount)
        hero.rested = True
        hero.statuses.rest_tick()
        self._note(f"{hero.name} · 휴식 · 카드 {drawn}장 보충, 적의 표적이 될 확률 감소")
        self.active = None
        self.order_index += 1
        self._prepare_actor()

    @staticmethod
    def _is_rest_locked(hero: PlayerCharacter) -> bool:
        return hero.statuses.has("rest_lock")

    def timing_progress(self, now: float | None = None) -> float:
        current = time.monotonic() if now is None else now
        travel = ((current - self.timing_start) * self.timing_speed) % 2
        return travel if travel <= 1 else 2 - travel

    def submit_timing(self, now: float | None = None) -> str:
        if self.phase not in ("attack_timing", "defense_timing"):
            return ""
        progress = self.timing_progress(now)
        distance = abs(progress - self.timing_center)
        if distance <= self.perfect_window:
            quality = "PERFECT"
        elif distance <= self.good_window:
            quality = "GOOD"
        else:
            quality = "MISS"
        self._resolve_timing(quality)
        return quality

    def _resolve_timing(self, quality: str) -> None:
        if self.phase == "attack_timing":
            self._resolve_player_attack(quality)
        elif self.phase == "defense_timing":
            self._resolve_enemy_attack(quality)

    def _resolve_player_attack(self, quality: str) -> None:
        hero, card, target = self.active, self.selected_card, self.attack_target
        if not hero or not card or not target:
            return
        multiplier = {
            "MISS": self.MISS_MULTIPLIER,
            "GOOD": self.GOOD_MULTIPLIER,
            "PERFECT": self.PERFECT_MULTIPLIER,
        }[quality]
        weak = hero.statuses.consume("weak")
        weak_scale = max(0.45, 1 - weak.amount) if weak else 1.0
        stack_scale = 1 + hero.perfect_stacks * 0.12 if hero.unit_id == "D" else 1.0
        damage = hero.attack * card.power * multiplier * weak_scale * stack_scale
        dealt = target.receive_hit(damage)
        hero.make_discard(card)
        if hero.unit_id == "D":
            if quality == "PERFECT":
                hero.perfect_stacks += 1
            else:
                hero.perfect_stacks = 0
        if quality in ("GOOD", "PERFECT") and card.status_key and target.alive:
            target.statuses.apply(card.status_key, card.status_turns, card.status_amount)
        self._show_result(f"{quality}  ·  {dealt} 피해", quality)
        self._note(f"{hero.name} · {card.name} · {quality} · {dealt} 피해 → {target.name}")
        if not target.alive:
            self._note(f"{target.name} 처치")
        self.phase = "result"
        self.result_after = "actor"
        self.result_until = time.monotonic() + 0.9

    def _resolve_enemy_attack(self, quality: str) -> None:
        source, target, skill = self.incoming_source, self.incoming_target, self.incoming_skill
        if not source or not target or not skill:
            return
        weak = source.statuses.consume("weak")
        weak_scale = max(0.45, 1 - weak.amount) if weak else 1.0
        if quality == "MISS":
            damage = target.receive_hit(source.attack * skill.power * weak_scale)
            text = f"MISS  ·  {damage} 피해"
            self._note(f"방어 실패 · {target.name}이 {damage} 피해를 받았습니다.")
        elif quality == "PERFECT" and target.unit_id == "B":
            damage = 0
            text = "PERFECT DODGE  ·  회피"
            self._note("B · PERFECT 회피로 피해를 받지 않았습니다.")
        else:
            damage = target.receive_hit(source.attack * skill.power * weak_scale * 0.5)
            text = f"{quality} GUARD  ·  {damage} 피해"
            self._note(f"방어 성공 · {target.name}이 피해를 절반으로 줄였습니다.")
        if damage and quality == "MISS" and skill.status_key and target.alive:
            target.statuses.apply(skill.status_key, 1, skill.status_amount)
            self._note(f"{target.name} · {skill.short_effect()} 상태가 적용되었습니다.")
        self._show_result(text, quality)
        self.phase = "result"
        self.result_after = "actor"
        self.result_until = time.monotonic() + 0.9

    def _show_result(self, text: str, quality: str) -> None:
        self.result_text = text
        self.result_color = {
            "PERFECT": (238, 204, 117),
            "GOOD": (133, 218, 181),
            "MISS": (230, 132, 123),
        }[quality]

    def update(self, now: float | None = None) -> None:
        current = time.monotonic() if now is None else now
        if self.phase in ("attack_timing", "defense_timing") and current - self.timing_start > 4.0 / max(0.5, self.timing_speed):
            self._resolve_timing("MISS")
        elif self.phase == "result" and current >= self.result_until:
            self.active = None
            self.selected_card = None
            self.attack_target = None
            self.incoming_source = None
            self.incoming_target = None
            self.incoming_skill = None
            self.order_index += 1
            self._prepare_actor()

    def reset(self) -> None:
        self.__init__(self.character_ids, self.encounter_id)

