"""One-floor route graph and its unlock/clear rules."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MapNode:
    node_id: str
    title: str
    kind: str
    x: int
    y: int
    next_nodes: tuple[str, ...] = ()
    unlocked: bool = False
    cleared: bool = False
    encounter_id: str | None = None

    @property
    def state(self) -> str:
        if self.cleared:
            return "cleared"
        return "available" if self.unlocked else "locked"


class FloorOne:
    """A single first-floor map with one route fork and a terminal boss."""

    floor_number = 1
    floor_title = "1층 · 잿빛 회랑"
    reward_sources: tuple[tuple[str, str], ...] = ()
    edges = (
        ("entrance", "battle_1"),
        ("battle_1", "battle_2"),
        ("battle_1", "elite"),
        ("battle_2", "shop"),
        ("elite", "shop"),
        ("shop", "boss"),
    )

    def __init__(self) -> None:
        self.nodes = {
            "entrance": MapNode("entrance", "출발 지점", "start", 865, 145, ("battle_1",), unlocked=True, cleared=True),
            "battle_1": MapNode("battle_1", "잿빛 회랑", "battle", 865, 310, ("battle_2", "elite"), unlocked=True, encounter_id="corridor"),
            "battle_2": MapNode("battle_2", "유리 숲길", "battle", 625, 475, ("shop",), encounter_id="corridor"),
            "elite": MapNode("elite", "유리 파수꾼", "elite", 1105, 475, ("shop",), encounter_id="floor1_elite"),
            "shop": MapNode("shop", "떠돌이 상점", "shop", 865, 640, ("boss",)),
            "boss": MapNode("boss", "1층 수호자", "boss", 865, 785, encounter_id="floor1_boss"),
        }
        self.is_complete = False

    def complete_node(self, node_id: str) -> bool:
        node = self.nodes[node_id]
        if not node.unlocked or node.cleared:
            return False
        node.cleared = True
        if node_id in ("battle_2", "elite"):
            other_branch = "elite" if node_id == "battle_2" else "battle_2"
            self.nodes[other_branch].unlocked = False
        for next_id in node.next_nodes:
            self.nodes[next_id].unlocked = True
        if node_id == "boss":
            self.is_complete = True
        return True


class FloorTwo:
    """Three-lane second-floor route with battles, elites, rewards and shops."""

    floor_number = 2
    floor_title = "2층 · 망각의 서고"
    reward_sources = (
        ("서리 감시자", "frost_sentinel"),
        ("잿불 추적자", "ember_stalker"),
        ("룬 결투가", "rune_duelist"),
        ("안개 궁수", "mist_archer"),
        ("강철 감시자", "iron_watcher"),
        ("폭풍 사냥개", "storm_hound"),
        ("가시 관리인", "thorn_custodian"),
        ("룬 수확자", "rune_reaper"),
        ("서리 집행관", "frost_champion"),
    )
    edges = (
        ("entrance2", "battle_a"),
        ("battle_a", "elite_a"),
        ("battle_a", "battle_b"),
        ("elite_a", "reward_a"),
        ("battle_b", "reward_a"),
        ("battle_b", "shop_a"),
        ("reward_a", "elite_b"),
        ("shop_a", "elite_b"),
        ("elite_b", "battle_c"),
        ("elite_b", "reward_b"),
        ("battle_c", "elite_c"),
        ("reward_b", "elite_c"),
        ("elite_c", "shop_b"),
        ("shop_b", "boss2"),
    )
    branch_groups = (
        ("elite_a", "battle_b"),
        ("reward_a", "shop_a"),
        ("battle_c", "reward_b"),
    )

    def __init__(self) -> None:
        left, center, right = 430, 865, 1300
        self.nodes = {
            "entrance2": MapNode("entrance2", "시작", "start", center, 145, ("battle_a",), unlocked=True, cleared=True),
            "battle_a": MapNode("battle_a", "서고 진입로", "battle", right, 215, ("elite_a", "battle_b"), unlocked=True, encounter_id="floor2_battle_a"),
            "elite_a": MapNode("elite_a", "가시의 방", "elite", left, 285, ("reward_a",), encounter_id="floor2_elite_a"),
            "battle_b": MapNode("battle_b", "봉인 회랑", "battle", right, 285, ("reward_a", "shop_a"), encounter_id="floor2_battle_b"),
            "reward_a": MapNode("reward_a", "기록 보관함", "reward", left, 355, ("elite_b",)),
            "shop_a": MapNode("shop_a", "기록 상점", "shop", right, 355, ("elite_b",)),
            "elite_b": MapNode("elite_b", "룬의 방", "elite", right, 425, ("battle_c", "reward_b"), encounter_id="floor2_elite_b"),
            "battle_c": MapNode("battle_c", "서리 서고", "battle", left, 495, ("elite_c",), encounter_id="floor2_battle_c"),
            "reward_b": MapNode("reward_b", "봉인 해제", "reward", right, 495, ("elite_c",)),
            "elite_c": MapNode("elite_c", "망각의 방", "elite", right, 565, ("shop_b",), encounter_id="floor2_elite_c"),
            "shop_b": MapNode("shop_b", "마지막 상점", "shop", center, 705, ("boss2",)),
            "boss2": MapNode("boss2", "기록의 관리자", "boss", center, 775, encounter_id="floor2_boss"),
        }
        self.is_complete = False

    def complete_node(self, node_id: str) -> bool:
        node = self.nodes[node_id]
        if not node.unlocked or node.cleared:
            return False
        node.cleared = True
        for group in self.branch_groups:
            if node_id in group:
                for alternative in group:
                    if alternative != node_id:
                        self.nodes[alternative].unlocked = False
        for next_id in node.next_nodes:
            self.nodes[next_id].unlocked = True
        if node.kind == "boss":
            self.is_complete = True
        return True
