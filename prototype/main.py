"""Launch the REDITUS ARCANUM Pico2D battle-stage prototype."""

from __future__ import annotations

import time
from pathlib import Path

import pico2d as p2d

from battle import Battle
from ui import BattleScreen, HEIGHT, WIDTH


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    p2d.open_canvas(WIDTH, HEIGHT)
    try:
        core = p2d.pico2d
        if getattr(core, "window", None) and getattr(core, "SDL_SetWindowTitle", None):
            core.SDL_SetWindowTitle(core.window, "REDITUS ARCANUM · BATTLE".encode("utf-8"))
        screen = BattleScreen(project_root)
        battle = Battle()
        running = True
        while running:
            frame_start = time.monotonic()
            for event in p2d.get_events():
                if event.type == p2d.SDL_QUIT:
                    running = False
                elif event.type == p2d.SDL_KEYDOWN:
                    if event.key == p2d.SDLK_ESCAPE:
                        running = False
                    elif event.key in (p2d.SDLK_SPACE, p2d.SDLK_RETURN):
                        battle.submit_timing()
                elif event.type == p2d.SDL_MOUSEBUTTONDOWN and event.button == p2d.SDL_BUTTON_LEFT:
                    screen.handle_click(battle, round(event.x / (WIDTH / 1440)), round((HEIGHT - event.y) / (HEIGHT / 960)))
            now = time.monotonic()
            battle.update(now)
            screen.draw(battle, now)
            elapsed = time.monotonic() - frame_start
            if elapsed < 1 / 60:
                time.sleep(1 / 60 - elapsed)
    finally:
        p2d.close_canvas()


if __name__ == "__main__":
    main()
