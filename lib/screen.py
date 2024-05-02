import _thread
import gc

import asyncio
import framebuf

from fps_counter import FpsCounter
from sprite import Sprite
import micropython

class Screen:
    display: framebuf.FrameBuffer
    sprites: [Sprite]
    sprites_lock: None

    def __init__(self, display=None):
        self.sprites_lock = _thread.allocate_lock()
        self.sprites = []
        if display:
            self.display = display
        self.fps = FpsCounter()

    def add(self, sprite):
        with self.sprites_lock:
            self.sprites.append(sprite)

    async def refresh_display(self):
        try:
            while True:
                self.do_refresh()
                await asyncio.sleep(1/120)
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

    def check_mem(self):
        gc.collect()
        print(f"Free memory: {gc.mem_free():,} bytes")

    def mem_marker(self, msg=None):
        gc.collect()
        print(msg)
        print(micropython.mem_info())



