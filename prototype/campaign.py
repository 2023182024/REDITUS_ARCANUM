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

    @property
    def state(self) -> str:
        if self.cleared:
            return "cleared"
        return "available" if self.unlocked else "locked"


class FloorOne:
    """A single first-floor map with one route fork and a terminal boss."""

    floor_number = 1
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
            "battle_1": MapNode("battle_1", "잿빛 회랑", "battle", 865, 310, ("battle_2", "elite"), unlocked=True),
            "battle_2": MapNode("battle_2", "유리 숲길", "battle", 625, 475, ("shop",)),
            "elite": MapNode("elite", "유리 파수꾼", "elite", 1105, 475, ("shop",)),
            "shop": MapNode("shop", "떠돌이 상점", "shop", 865, 640, ("boss",)),
            "boss": MapNode("boss", "1층 수호자", "boss", 865, 785),
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
