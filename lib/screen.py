import _thread
import gc
import utime
import uasyncio as asyncio

from fps_counter import FpsCounter
from sprites.sprite import Sprite
import micropython

# from ssd1331_pio import SSD1331PIO
# from double_buffer_driver import DoubleBufferDriver

class Screen:
    display = None
    sprites: [Sprite]
    last_tick: int = 0
    last_gc: int = 0
    gc_interval: int = 3000 # how often to call the garbage collector (ms)
    app: None # ref to ScreenApp
    profile_labels = {}

    def __init__(self, display=None):
        self.sprites = []
        if display:
            self.display = display
        self.fps = FpsCounter()

    def add(self, sprite):
        self.sprites.append(sprite)

    async def refresh_display(self):
        wait_s = 1/90
        try:
            while True:
                self.do_refresh()
                now = utime.ticks_ms()

                if (now - self.last_gc) > self.gc_interval:
                    gc.collect()
                    self.last_gc = utime.ticks_ms()

                await asyncio.sleep(wait_s)
        except asyncio.CancelledError:
            return True

    def start_display_loop(self):
        loop = asyncio.get_event_loop()
        self.display_task = loop.create_task(self.refresh_display())

    async def start_main_loop(self):
        await asyncio.gather(
            self.update_loop(),
        )

    def do_refresh(self):
        """blocking, non-looping, version of refresh_display(), for when you need a refresh in a specific
        place in the code"""
        self.display.show()
        self.last_tick = self.fps.tick()

    def draw_sprites(self):
        for my_sprite in self.sprites:
            my_sprite.show(self.display)


    def check_mem(self):
        gc.collect()
        print(f"Free memory: {gc.mem_free():,} bytes")

    def mem_marker(self, msg=None):
        gc.collect()
        print(msg)
        print(micropython.mem_info())