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
        ("battle_1", "shop"),
        ("battle_2", "boss"),
        ("shop", "boss"),
    )

    def __init__(self) -> None:
        self.nodes = {
            "entrance": MapNode("entrance", "출발 지점", "start", 865, 145, ("battle_1",), unlocked=True, cleared=True),
            "battle_1": MapNode("battle_1", "잿빛 회랑", "battle", 865, 330, ("battle_2", "shop"), unlocked=True),
            "battle_2": MapNode("battle_2", "유리 숲길", "battle", 625, 535, ("boss",)),
            "shop": MapNode("shop", "떠돌이 상점", "shop", 1105, 535, ("boss",)),
            "boss": MapNode("boss", "1층 수호자", "boss", 865, 755),
        }
        self.is_complete = False

    def complete_node(self, node_id: str) -> bool:
        node = self.nodes[node_id]
        if not node.unlocked or node.cleared:
            return False
        node.cleared = True
        if node_id == "battle_2":
            self.nodes["shop"].unlocked = False
        elif node_id == "shop":
            self.nodes["battle_2"].unlocked = False
        for next_id in node.next_nodes:
            self.nodes[next_id].unlocked = True
        if node_id == "boss":
            self.is_complete = True
        return True
