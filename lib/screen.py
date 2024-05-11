import gc

import asyncio

from fps_counter import FpsCounter
from sprites.sprite import Sprite
import micropython

from ssd1331_16bit import SSD1331


class Screen:
    display: SSD1331
    sprites: [Sprite]
    last_tick: int = 0
    gc_interval: int = 10 # how often to call the garbage collector

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
                if (self.last_tick % self.gc_interval) == 0:
                    gc.collect()

                await asyncio.sleep(1/500)
        except asyncio.CancelledError:
            return True

    def do_refresh(self):
        """Synchronous, non-looping, version of refresh_display()"""
        self.display.show()
        self.last_tick = self.fps.tick()

    def draw_sprites(self):
        for my_sprite in self.sprites:
            my_sprite.show(self.display)

    async def update_fps(self):
        while True:
            # Show the FPS in the score label
            fps = int(self.fps.fps())
            await asyncio.sleep(0.3)

    def check_mem(self):
        gc.collect()
        print(f"Free memory: {gc.mem_free():,} bytes")

    def mem_marker(self, msg=None):
        gc.collect()
        print(msg)
        print(micropython.mem_info())



