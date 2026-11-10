"""Title, character selection, and first-floor map screens."""

from __future__ import annotations

from campaign import FloorOne
from units import character_info
from ui import BattleScreen, DESIGN_HEIGHT, DESIGN_WIDTH, GOLD, INK, LINE, MUTED, PANEL, PANEL_LIGHT, TEXT

import pico2d as p2d


class CampaignScreen(BattleScreen):
    def __init__(self, asset_root):
        super().__init__(asset_root)
        self.start_rect = (535, 230, 905, 325)
        self.confirm_rect = (540, 125, 900, 205)
        self.character_rects: dict[str, tuple[int, int, int, int]] = {}
        self.map_node_rects: dict[str, tuple[int, int, int, int]] = {}
        self.map_restart_rect = (50, 868, 202, 910)
        self.complete_rect = (540, 245, 900, 330)

    def _clear_page(self) -> None:
        p2d.clear_canvas()
        self.rect(0, 0, DESIGN_WIDTH, DESIGN_HEIGHT, INK)

    def draw_title(self) -> None:
        self._clear_page()
        self.circle(720, 540, 260, (27, 35, 52), filled=True)
        self.circle(720, 540, 235, (48, 43, 52), filled=False)
        self.image(self.portraits["D"], 720, 520, 238, 357)
        self.text(720, 830, "REDITUS ARCANUM", 38, TEXT, centered=True)
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

    def draw_map(self, floor_map: FloorOne, character_id: str, notice: str = "") -> None:
        self._clear_page()
        self.map_node_rects.clear()
        self.text(875, 905, "1층 · 잿빛 회랑", 28, TEXT, centered=True)
        self.panel(self.map_restart_rect[0], self.map_restart_rect[1], self.map_restart_rect[2] - self.map_restart_rect[0], self.map_restart_rect[3] - self.map_restart_rect[1], PANEL_LIGHT, LINE)
        self.text((self.map_restart_rect[0] + self.map_restart_rect[2]) / 2, 889, "처음으로", 13, MUTED, centered=True)

        self._draw_route_panel(character_id)
        for source_id, target_id in floor_map.edges:
            source = floor_map.nodes[source_id]
            target = floor_map.nodes[target_id]
            color = (107, 99, 76) if source.cleared or target.unlocked else (49, 57, 71)
            self.line(source.x, source.y, target.x, target.y, color)
        for node in floor_map.nodes.values():
            self._draw_map_node(node)

        self.text(875, 91, "진행 가능한 노드를 선택하세요", 14, MUTED, centered=True)
        if notice:
            self.panel(510, 842, 730, 38, (50, 45, 39), GOLD)
            self.text(875, 861, notice[:62], 13, GOLD, centered=True)
        p2d.update_canvas()

    def _draw_route_panel(self, character_id: str) -> None:
        data = character_info(character_id)
        self.panel(34, 215, 286, 620, PANEL)
        self.text(177, 800, "현재 동행자", 17, GOLD, centered=True)
        self.image(self.portraits[character_id], 177, 627, 154, 231)
        self.text(177, 487, data["name"], 17, data["accent"], centered=True)
        self.text(58, 443, f"HP  {data['hp']}", 14, TEXT)
        self.text(58, 414, f"ATK {data['attack']}   ·   SPD {data['speed']}", 13, MUTED)
        self.text(58, 362, data["trait"], 13, MUTED)
        self.text(58, 286, "층 진행  1 / 1", 15, GOLD)
        self.text(58, 253, "다음 층은 이 프로토타입에", 12, MUTED)
        self.text(58, 233, "포함되지 않습니다.", 12, MUTED)

    def _draw_map_node(self, node) -> None:
        if node.kind == "start":
            w, h = 210, 78
            accent = (112, 174, 152)
        else:
            w, h = 230, 108
            accent = {"battle": (203, 126, 110), "shop": (134, 159, 201), "boss": GOLD}[node.kind]
        rect = (node.x - w // 2, node.y - h // 2, node.x + w // 2, node.y + h // 2)
        self.map_node_rects[node.node_id] = rect
        state = node.state
        edge = GOLD if state == "available" else (97, 143, 118) if state == "cleared" else LINE
        fill = (48, 45, 40) if state == "available" else (31, 43, 42) if state == "cleared" else PANEL
        self.panel(rect[0], rect[1], w, h, fill, edge)
        self.text(node.x, node.y + 23, node.title, 19 if node.kind != "start" else 16, accent if state != "locked" else MUTED, centered=True)
        if node.kind == "start":
            status = "시작"
        elif node.kind == "shop":
            status = "상점 · 구매 기능 미구현" if state != "locked" else "잠김"
        else:
            kind_label = {"battle": "전투", "boss": "층 보스"}[node.kind]
            status_label = {"available": "진행 가능", "cleared": "완료", "locked": "잠김"}[state]
            status = f"{kind_label}  ·  {status_label}"
        self.text(node.x, node.y - 15, status, 13, GOLD if state == "available" else MUTED, centered=True)

    def draw_floor_complete(self) -> None:
        self._clear_page()
        self.circle(720, 565, 190, (47, 43, 38), filled=True)
        self.text(720, 620, "1층 클리어", 38, GOLD, centered=True)
        self.text(720, 558, "현재 플레이 가능한 맵은 1층까지입니다.", 17, TEXT, centered=True)
        self.panel(self.complete_rect[0], self.complete_rect[1], self.complete_rect[2] - self.complete_rect[0], self.complete_rect[3] - self.complete_rect[1], (52, 48, 42), GOLD)
        self.text(720, 278, "타이틀로", 20, GOLD, centered=True)
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

    def map_node_at(self, x: int, y: int, floor_map: FloorOne) -> str | None:
        for node_id, rect in self.map_node_rects.items():
            if floor_map.nodes[node_id].unlocked and not floor_map.nodes[node_id].cleared and self._inside(x, y, rect):
                return node_id
        return None

    def map_restart_clicked(self, x: int, y: int) -> bool:
        return self._inside(x, y, self.map_restart_rect)

    def floor_complete_clicked(self, x: int, y: int) -> bool:
        return self._inside(x, y, self.complete_rect)
