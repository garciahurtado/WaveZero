import asyncio
import framebuf

from fps_counter import FpsCounter
from road_grid import RoadGrid
from sprite import Sprite


class Screen:
    display: framebuf.FrameBuffer
    grid: RoadGrid
    sprites: [Sprite]

    def __init__(self, display=None):
        self.sprites = []
        if display:
            self.display = display
        self.fps = FpsCounter()

    def add(self, sprite):
        self.sprites.append(sprite)

    async def refresh_display(self):
        try:
            while True:
                self.do_refresh()
                await asyncio.sleep(1/90)
        except asyncio.CancelledError:
            return True

    def do_refresh(self):
        """Synchronous, non-looping, version of refresh_display()"""
        self.display.show()
        self.fps.tick()

    def draw_sprites(self):
        for my_sprite in self.sprites:
            my_sprite.show(self.display)

    async def update_fps(self):
        while True:
            # Show the FPS in the score label
            fps = int(self.fps.fps())
            await asyncio.sleep(0.2)

