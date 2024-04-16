import asyncio
import framebuf

from fps_counter import FpsCounter
from road_grid import RoadGrid
from ui_elements import ui_screen


class Screen:
    display: framebuf.FrameBuffer
    ui: ui_screen
    grid: RoadGrid

    def __init__(self, display=None):
        if display:
            self.display = display
            self.ui = ui_screen(self.display)
        self.fps = FpsCounter()

    async def refresh(self):
        while True:
            self.display.fill(0)
            self.grid.draw_horiz_lines()
            self.grid.draw_vert_lines()
            self.ui.refresh()
            self.fps.tick()
            await asyncio.sleep(0.001)

    def refresh_display(self):
        self.ui.refresh()
        self.fps.tick()