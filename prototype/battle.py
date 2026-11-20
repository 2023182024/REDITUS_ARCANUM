"""Turn order, card play, timing commands and battle resolution."""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, replace

from cards import SkillCard
from status_effects import StatusCollection
from units import Combatant, Enemy, PlayerCharacter, create_enemies, create_party


@dataclass
class TurnEntry:
    actor: Combatant
    die: int


@dataclass(frozen=True)
class AttackEffectState:
    source_id: str
    target_id: str
    source_side: str
    quality: str
    started_at: float


@dataclass(frozen=True)
class DefenseEffectState:
    target_id: str
    effect_key: str
    started_at: float


class Battle:
    ENEMY_SKILL_REVEAL_DURATION = 1.5
    MULTI_HIT_GAP = 0.42
    PLAYER_SPEED_SHIFT = 15
    FOCUS_TIMING_SPEED_SCALE = 0.75
    LUMIEL_GUARD_REDUCTION = 0.25
    VULNERABLE_AMOUNT = 0.25
    BLEED_AMOUNT = 7
    BLEED_TURNS = 2
    PERFECT_MULTIPLIER = 1.6
    GOOD_MULTIPLIER = 1.0
    MISS_MULTIPLIER = 0.5

    def __init__(
        self,
        character_ids: list[str] | None = None,
        encounter_id: str = "corridor",
        decks: dict[str, list[SkillCard]] | None = None,
        relic_ids: list[str] | None = None,
        roster: list[PlayerCharacter] | None = None,
    ) -> None:
        self.character_ids = (
            [hero.unit_id for hero in roster]
            if roster is not None
            else list(character_ids) if character_ids is not None else list("ABCD")
        )
        self.encounter_id = encounter_id
        self.relic_ids = list(relic_ids or [])
        self.deck_templates = {
            character_id: [replace(card) for card in decks[character_id]]
            for character_id in self.character_ids
            if decks and character_id in decks
        }
        if roster is None:
            self.party = create_party(self.character_ids, self.deck_templates)
        else:
            self.party = roster
            for hero in self.party:
                hero.deck.extend(hero.hand)
                hero.deck.extend(hero.discard)
                random.shuffle(hero.deck)
                hero.hand.clear()
                hero.discard.clear()
                hero.draw(3)
                hero.alive = hero.hp > 0
                hero.statuses = StatusCollection()
                hero.rested = False
                hero.perfect_stacks = 0
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
        self.enemy_skill_reveal_started_at = 0.0
        self.timing_start = time.monotonic()
        self.timing_speed = 1.0
        self.timing_center = 0.5
        self.perfect_window = 0.055
        self.good_window = 0.17
        self.timing_bonus = 0.0
        self.attack_hit_index = 0
        self.attack_hit_qualities: list[str] = []
        self.attack_internal_bonus = 0.0
        self.attack_weak_scale = 1.0
        self.attack_base_bonus_pct = 0.0
        self.attack_timing_speed_scale = 1.0
        self.next_attack_timing_speed_scale: dict[str, float] = {}
        self.next_speed_adjustments: dict[str, int] = {}
        self.guard_reduction_by_id: dict[str, tuple[int, float]] = {}
        self.multi_hit_next_at = 0.0
        self.result_quality = "GOOD"
        self.result_color = (240, 236, 218)
        self.result_target_id: str | None = None
        self.result_damage = 0
        self.result_started_at = 0.0
        self.attack_effect: AttackEffectState | None = None
        self.defense_effect: DefenseEffectState | None = None
        self.result_until = 0.0
        self.log_lines: list[str] = []
        self.roll_by_id: dict[str, int] = {}
        self.rng = random.Random()
        self.pending_speed_bonus_ids: set[str] = set()
        self.first_allied_actor_id: str | None = None
        self.first_ally_attack_used = False
        self.first_enemy_kill_extra_used = False
        self.empty_hand_relic_used = False
        self.fortune_coin_used = False
        self.pending_extra_actions: list[PlayerCharacter] = []
        self.immortal_goblet_used = False
        self.life_crystal_used_ids: set[str] = set()
        self.time_shard_used_ids: set[str] = set()
        self.next_attack_bonus_pct: dict[str, float] = {}
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

    def _has_relic(self, relic_id: str) -> bool:
        return relic_id in self.relic_ids

    def _queue_extra_action(self, hero: PlayerCharacter) -> None:
        if not self.order or self.order_index >= len(self.order):
            self.pending_extra_actions.append(hero)
        else:
            self.order.insert(
                self.order_index + 1,
                TurnEntry(hero, self.roll_by_id.get(hero.unit_id, 1)),
            )
        self._note(f"{hero.name} · 유물 효과로 추가 행동을 얻었습니다.")

    def _receive_hit(self, target: Combatant, damage: float) -> int:
        previous_hp = target.hp
        amount = target.receive_hit(damage)
        if not isinstance(target, PlayerCharacter):
            return amount

        if not target.alive and self._has_relic("immortal_goblet") and not self.immortal_goblet_used:
            self.immortal_goblet_used = True
            target.hp = min(target.max_hp, 1 + round(target.max_hp * 0.1))
            target.alive = True
            self._note(f"불멸의 성배 · {target.name}이 치명상을 버티고 회복했습니다.")

        crossed_low_health = (
            amount > 0
            and previous_hp > target.max_hp * 0.3
            and target.hp > 0
            and target.hp <= target.max_hp * 0.3
        )
        if crossed_low_health and self._has_relic("life_crystal") and target.unit_id not in self.life_crystal_used_ids:
            self.life_crystal_used_ids.add(target.unit_id)
            recovery = round(target.max_hp * 0.3)
            target.hp = min(target.max_hp, target.hp + recovery)
            self._note(f"생명의 수정 · {target.name} 체력 {recovery} 회복")
        if crossed_low_health and self._has_relic("time_shard") and target.unit_id not in self.time_shard_used_ids:
            self.time_shard_used_ids.add(target.unit_id)
            self._queue_extra_action(target)
            self._note(f"시간의 파편 · {target.name}이 다음 행동을 얻었습니다.")
        return amount

    def _build_order(self) -> None:
        actors = [unit for unit in (*self.party, *self.enemies) if unit.alive]
        self.roll_by_id = {unit.unit_id: self.rng.randint(1, 6) for unit in actors}
        def order_speed(unit: Combatant) -> int:
            bonus = round(unit.speed * 0.1) if unit.unit_id in self.pending_speed_bonus_ids else 0
            return unit.effective_speed() + bonus + self.next_speed_adjustments.get(unit.unit_id, 0)

        actors.sort(key=lambda unit: (-order_speed(unit), -self.roll_by_id[unit.unit_id]))
        self.order = [TurnEntry(unit, self.roll_by_id[unit.unit_id]) for unit in actors]
        if self.round == 1:
            self.first_allied_actor_id = next(
                (entry.actor.unit_id for entry in self.order if isinstance(entry.actor, PlayerCharacter)),
                None,
            )
            if "fortune_coin" in self.relic_ids and not self.fortune_coin_used and self.party:
                favored = self.rng.choice(self.party)
                favored_index = next(
                    index for index, entry in enumerate(self.order) if entry.actor is favored
                )
                self.order.insert(favored_index + 1, TurnEntry(favored, self.roll_by_id[favored.unit_id]))
                self.fortune_coin_used = True
        for hero in self.pending_extra_actions:
            hero_index = next(
                (index for index, entry in enumerate(self.order) if entry.actor is hero),
                None,
            )
            if hero_index is not None:
                self.order.insert(hero_index + 1, TurnEntry(hero, self.roll_by_id[hero.unit_id]))
        self.pending_extra_actions.clear()
        self.pending_speed_bonus_ids.clear()
        self.next_speed_adjustments.clear()
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
            if self.phase in ("enemy_skill_reveal", "defense_timing"):
                return

    def _end_round(self) -> None:
        for unit in (*self.party, *self.enemies):
            if not unit.alive:
                continue
            bleed_damage, removed = unit.statuses.end_round()
            if bleed_damage:
                if isinstance(unit, PlayerCharacter):
                    self._receive_hit(unit, bleed_damage)
                else:
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
        self.enemy_skill_reveal_started_at = time.monotonic()
        self.timing_speed = skill.timing_speed
        self.timing_center = 0.5
        bonus = 0.04 if target.unit_id == "A" else 0
        self.timing_bonus = bonus
        self.perfect_window = 0.055 + bonus
        self.good_window = 0.17 + bonus
        self.phase = "enemy_skill_reveal"
        self.active = None
        self._note(f"{enemy.name} · {skill.name} 공개 · {target.name} 대상")

    def begin_attack(self, hero: PlayerCharacter, card: SkillCard, target: Enemy) -> None:
        if self.phase != "player" or hero is not self.active:
            return
        if card not in hero.hand or not target.alive:
            return
        hero.hand.remove(card)
        self.selected_card = card
        self.attack_target = target
        now = time.monotonic()
        self.timing_start = now
        self.attack_hit_index = 0
        self.attack_hit_qualities = []
        self.attack_internal_bonus = 0.0
        self.attack_weak_scale = 1.0
        self.attack_base_bonus_pct = self.next_attack_bonus_pct.pop(hero.unit_id, 0.0)
        self.attack_timing_speed_scale = self.next_attack_timing_speed_scale.pop(hero.unit_id, 1.0)
        self.timing_speed = card.timing_speed * self.attack_timing_speed_scale
        self.timing_center = 0.5
        bonus = 0.045 if hero.unit_id == "A" else 0
        self.perfect_window = card.perfect_window + bonus
        self.good_window = card.good_window + bonus
        self.timing_bonus = bonus
        self.phase = "hold_wait" if card.hold_to_judge else "attack_timing"
        if not hero.hand and self._has_relic("cycle_compass") and not self.empty_hand_relic_used:
            self.empty_hand_relic_used = True
            drawn = hero.draw(1)
            if drawn:
                self._note(f"순환의 나침반 · {hero.name}이 카드 1장을 뽑았습니다.")
        if card.hold_to_judge:
            self._note(f"{hero.name} · {card.name} · SPACE를 누르고 있다가 놓아 판정")
        elif card.hit_count > 1:
            self._note(f"{hero.name} · {card.name} · {card.hit_count}회 연속 판정")
        else:
            self._note(f"{hero.name} · {card.name} · SPACE로 타이밍 입력")

    def start_hold_timing(self, now: float | None = None) -> bool:
        if self.phase != "hold_wait" or not self.selected_card or not self.selected_card.hold_to_judge:
            return False
        self.timing_start = time.monotonic() if now is None else now
        self.phase = "hold_timing"
        self._note(f"{self.selected_card.name} · SPACE를 놓으면 판정")
        return True

    def release_hold_timing(self, now: float | None = None) -> str:
        if self.phase != "hold_timing":
            return ""
        self.phase = "attack_timing"
        return self.submit_timing(now)

    def select_card(self, hero: PlayerCharacter, card: SkillCard) -> None:
        if self.phase != "player" or hero is not self.active or card not in hero.hand:
            return
        self.selected_card = card
        self._note(f"선택 · {card.name} · 화살표로 적을 골라 SPACE를 누르세요.")

    def cancel_card_selection(self, hero: PlayerCharacter) -> bool:
        if self.phase != "player" or hero is not self.active or not self.selected_card:
            return False
        card = self.selected_card
        self.selected_card = None
        self.attack_target = None
        self._note(f"{hero.name} · {card.name} 대상 선택을 취소했습니다.")
        return True

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
        if (
            self._has_relic("old_pen")
            and len(hero.hand) < 5
            and self.rng.random() < 0.1
        ):
            extra_drawn = hero.draw(1)
            drawn += extra_drawn
            if extra_drawn:
                self._note(f"낡은 만년필 · {hero.name}이 카드 1장을 추가로 뽑았습니다.")
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
        if self.phase in ("hold_wait", "multi_hit_pause"):
            return 0.0
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
        if self.phase in ("attack_timing", "hold_timing"):
            self._resolve_player_attack(quality)
        elif self.phase == "defense_timing":
            self._resolve_enemy_attack(quality)

    def _resolve_player_attack(self, quality: str) -> None:
        hero, card, target = self.active, self.selected_card, self.attack_target
        if not hero or not card or not target:
            return
        if self.attack_hit_index == 0:
            weak = hero.statuses.consume("weak")
            self.attack_weak_scale = max(0.45, 1 - weak.amount) if weak else 1.0
            if (
                hero.unit_id == self.first_allied_actor_id
                and not self.first_ally_attack_used
                and self._has_relic("first_strike_charm")
            ):
                self.attack_base_bonus_pct += 0.15
                self.first_ally_attack_used = True
        multiplier = {
            "MISS": self.MISS_MULTIPLIER,
            "GOOD": self.GOOD_MULTIPLIER,
            "PERFECT": self.PERFECT_MULTIPLIER,
        }[quality]
        stack_rate = 0.12 * (1.5 if card.effect_key == "karmina_karma" else 1.0)
        stack_scale = 1 + hero.perfect_stacks * stack_rate if hero.unit_id == "D" else 1.0
        relic_bonus_pct = self.attack_base_bonus_pct
        if quality == "PERFECT" and self._has_relic("precision_clock"):
            relic_bonus_pct += 0.10
        if target.hp >= target.max_hp * 0.5 and self._has_relic("warrior_insignia"):
            relic_bonus_pct += 0.10
        if target.hp <= target.max_hp * 0.5 and self._has_relic("hunter_insignia"):
            relic_bonus_pct += 0.10
        damage = (
            hero.attack
            * card.power
            * multiplier
            * (1 + relic_bonus_pct + self.attack_internal_bonus)
            * self.attack_weak_scale
            * stack_scale
        )
        target_was_alive = target.alive
        dealt = target.receive_hit(damage)
        self._record_attack_effect(hero, target, quality)
        self.attack_hit_qualities.append(quality)

        if quality in ("GOOD", "PERFECT") and card.status_key and target.alive:
            target.statuses.apply(card.status_key, card.status_turns, card.status_amount)
        if card.effect_key == "karmina_twin_slash" and quality in ("GOOD", "PERFECT") and target.alive:
            bleed = self.BLEED_AMOUNT * (2 if quality == "PERFECT" else 1)
            target.statuses.apply("bleed", self.BLEED_TURNS, bleed)
        if card.effect_key == "karmina_assault" and quality == "PERFECT" and target.alive:
            target.statuses.apply("stun", 1)
        if card.effect_key == "lumiel_heal" and quality in ("GOOD", "PERFECT"):
            self._heal_lowest_party_member(round(dealt * 0.40))
        if card.effect_key == "lumiel_guard":
            for ally in self.living_party:
                if ally is not hero:
                    self.guard_reduction_by_id[ally.unit_id] = (self.round, self.LUMIEL_GUARD_REDUCTION)
        if card.effect_key == "lumiel_draw" and quality in ("GOOD", "PERFECT"):
            drawn = hero.draw(1)
            if drawn:
                self._note(f"순환의 노래 · {hero.name}이 카드 1장을 뽑았습니다.")
        if card.effect_key == "neira_triple_assault" and quality in ("GOOD", "PERFECT"):
            self.attack_internal_bonus += 0.03

        if hero.unit_id == "D":
            if quality == "PERFECT":
                hero.perfect_stacks += 1
            else:
                hero.perfect_stacks = 0
        self._show_result(quality, target, dealt)
        self._note(
            f"{hero.name} · {card.name} {self.attack_hit_index + 1}/{card.hit_count} · "
            f"{quality} · {dealt} 피해 → {target.name}"
        )

        if card.effect_key == "neira_spin":
            if quality == "MISS":
                self.next_speed_adjustments[hero.unit_id] = -self.PLAYER_SPEED_SHIFT
                self._note(f"회전 베기 실패 · 다음 순서 속도 -{self.PLAYER_SPEED_SHIFT}")
            elif quality == "PERFECT":
                self.next_speed_adjustments[hero.unit_id] = self.PLAYER_SPEED_SHIFT
                self._note(f"회전 베기 PERFECT · 다음 순서 속도 +{self.PLAYER_SPEED_SHIFT}")

        self.attack_hit_index += 1
        stop_chain = not target.alive or (card.stop_on_miss and quality == "MISS")
        has_more_hits = self.attack_hit_index < card.hit_count and not stop_chain
        if has_more_hits:
            self.multi_hit_next_at = time.monotonic() + self.MULTI_HIT_GAP
            self.phase = "multi_hit_pause"
            return

        if (
            card.effect_key == "adeline_double_slash"
            and target.alive
            and len(self.attack_hit_qualities) == card.hit_count
            and all(hit_quality == "PERFECT" for hit_quality in self.attack_hit_qualities)
        ):
            target.statuses.apply("vulnerable", 1, self.VULNERABLE_AMOUNT, hits=1)
            self._note(f"{target.name} · 취약 상태가 적용되었습니다.")
        if card.effect_key == "neira_focus":
            self.next_attack_timing_speed_scale[hero.unit_id] = self.FOCUS_TIMING_SPEED_SCALE
            self._note("집중 · 다음 공격의 게이지 속도가 감소합니다.")

        hero.make_discard(card)
        if not target.alive:
            self._note(f"{target.name} 처치")
            if (
                target_was_alive
                and self._has_relic("clockwork")
                and not self.first_enemy_kill_extra_used
            ):
                self.first_enemy_kill_extra_used = True
                self._queue_extra_action(hero)
        if "PERFECT" in self.attack_hit_qualities and self._has_relic("gale_compass"):
            self.pending_speed_bonus_ids.add(hero.unit_id)
        self.phase = "result"
        self.result_after = "actor"
        self.result_until = time.monotonic() + 0.9

    def _heal_lowest_party_member(self, amount: int) -> None:
        if amount <= 0 or not self.living_party:
            return
        target = min(self.living_party, key=lambda member: member.hp)
        healed = min(amount, target.max_hp - target.hp)
        if healed > 0:
            target.hp += healed
            self._note(f"치유의 파동 · {target.name} 체력 {healed} 회복")

    def _resolve_enemy_attack(self, quality: str) -> None:
        source, target, skill = self.incoming_source, self.incoming_target, self.incoming_skill
        if not source or not target or not skill:
            return
        self.defense_effect = None
        if quality in ("GOOD", "PERFECT"):
            effect_key = "avoid" if quality == "PERFECT" and target.unit_id == "B" else "guard"
            self.defense_effect = DefenseEffectState(target.unit_id, effect_key, time.monotonic())
        weak = source.statuses.consume("weak")
        weak_scale = max(0.45, 1 - weak.amount) if weak else 1.0
        guard = self.guard_reduction_by_id.get(target.unit_id)
        guard_scale = 1 - guard[1] if guard and guard[0] == self.round else 1.0
        if quality == "MISS":
            damage = self._receive_hit(target, source.attack * skill.power * weak_scale * guard_scale)
            self._note(f"방어 실패 · {target.name}이 {damage} 피해를 받았습니다.")
        elif quality == "PERFECT" and target.unit_id == "B":
            damage = 0
            self._note("B · PERFECT 회피로 피해를 받지 않았습니다.")
        else:
            damage = self._receive_hit(target, source.attack * skill.power * weak_scale * guard_scale * 0.5)
            self._note(f"방어 성공 · {target.name}이 피해를 절반으로 줄였습니다.")
        if guard_scale < 1 and damage:
            self._note(f"수호의 타종 · {target.name}이 추가 피해 감소 효과를 받았습니다.")
        if quality == "PERFECT" and self._has_relic("focus_crystal"):
            self.next_attack_bonus_pct[target.unit_id] = self.next_attack_bonus_pct.get(target.unit_id, 0.0) + 0.10
            self._note(f"집중의 수정 · {target.name}의 다음 공격 피해량이 증가합니다.")
        if quality == "PERFECT" and damage and self._has_relic("counter_bell") and source.alive:
            reflected = source.receive_hit(damage * 0.3)
            self._note(f"반격의 종 · {source.name}에게 {reflected} 피해를 반사했습니다.")
        if damage:
            self._record_attack_effect(source, target, quality)
        if damage and quality == "MISS" and skill.status_key and target.alive:
            target.statuses.apply(skill.status_key, skill.status_turns, skill.status_amount)
            self._note(f"{target.name} · {skill.short_effect()} 상태가 적용되었습니다.")
        self._show_result(quality, target, damage)
        self.phase = "result"
        self.result_after = "actor"
        self.result_until = time.monotonic() + 0.9

    def _record_attack_effect(
        self, source: Combatant, target: Combatant, quality: str
    ) -> None:
        self.attack_effect = AttackEffectState(
            source_id=source.unit_id,
            target_id=target.unit_id,
            source_side=source.side,
            quality=quality,
            started_at=time.monotonic(),
        )

    def _show_result(self, quality: str, target: Combatant, damage: int) -> None:
        self.result_quality = quality
        self.result_target_id = target.unit_id
        self.result_damage = damage
        self.result_started_at = time.monotonic()
        self.result_color = {
            "PERFECT": (238, 204, 117),
            "GOOD": (133, 218, 181),
            "MISS": (230, 132, 123),
        }[quality]

    def update(self, now: float | None = None) -> None:
        current = time.monotonic() if now is None else now
        if (
            self.phase == "enemy_skill_reveal"
            and current - self.enemy_skill_reveal_started_at >= self.ENEMY_SKILL_REVEAL_DURATION
        ):
            self.timing_start = current
            self.phase = "defense_timing"
            target_name = self.incoming_target.name if self.incoming_target else "아군"
            self._note(f"{target_name} 방어 판정 시작")
        elif self.phase == "multi_hit_pause" and current >= self.multi_hit_next_at:
            self.timing_start = current
            self.phase = "hold_wait" if self.selected_card and self.selected_card.hold_to_judge else "attack_timing"
        elif self.phase in ("attack_timing", "defense_timing", "hold_timing") and current - self.timing_start > 4.0 / max(0.5, self.timing_speed):
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
        self.__init__(
            self.character_ids,
            self.encounter_id,
            self.deck_templates,
            self.relic_ids,
            self.party,
        )

