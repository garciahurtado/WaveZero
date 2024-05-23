import gc

import utime

import asyncio

from fps_counter import FpsCounter
from sprites.sprite import Sprite
import micropython

from ssd1331_16bit import SSD1331
import ssd_1331

class Screen:
    display: SSD1331
    sprites: [Sprite]
    last_tick: int = 0
    last_gc: int = 0
    gc_interval: int = 500 # how often to call the garbage collector (ms)

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
                now = utime.ticks_ms()

                if (now - self.last_gc) > self.gc_interval:
                    gc.collect()
                    self.last_gc = utime.ticks_ms()

                await asyncio.sleep(1//1000)
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



