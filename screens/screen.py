import gc
import time

import utime
import uasyncio as asyncio
from ucollections import namedtuple

from fps_counter import FpsCounter
from sprites.sprite import Sprite
import micropython
from ssd1331_pio import SSD1331PIO

class Screen:
    debug = False
    display = None
    bounds = None
    margin_px = 0
    instances: [Sprite]
    last_gc: int = 0
    gc_interval: int = 3000 # how often to call the garbage collector (ms)
    # gc_interval = 0
    app: None # ref. to ScreenApp
    profile_labels = {}
    display_loop_wait = 2 # ms for the display loop to wait between refreshes
    fps = 0
    target_fps = 30
    total_width = 0
    total_height = 0

    def __init__(self, display:SSD1331PIO=None, margin_px=0):
        self.instances = []
        if display:
            self.display = display
            self.bounds = ScreenBounds(
                left = 0-margin_px,
                right= display.WIDTH + margin_px,
                top = 0-margin_px,
                bottom= display.HEIGHT + margin_px
            )
        self.margin_px = margin_px
        margin = self.margin_px
        display = self.display
        self.total_width = display.WIDTH + 2*margin  # Add margin on both sides
        self.total_height = display.HEIGHT + 2*margin

        self.fps = FpsCounter()
        self.last_gc = utime.ticks_ms()


    def add(self, sprite):
        self.instances.append(sprite)

    async def _refresh_display(self):
        # DEPRECATED?
        wait_s = 1/30# max FPS
        try:
            while True:
                self.do_refresh()
                # now = utime.ticks_ms()
                # if (now - self.last_gc) > self.gc_interval:
                #     gc.collect()
                #     self.last_gc = utime.ticks_ms()

                await asyncio.sleep(wait_s)
        except asyncio.CancelledError:
            return True

    async def start_display_loop(self):
        while True:
            self.do_refresh()
            await asyncio.sleep_ms(5)

    async def start_main_loop(self):
        await asyncio.gather(
            self.update_loop(),
        )

    def do_refresh(self):
        """blocking, non-looping, version of refresh_display(), for when you need a refresh in a specific
        place in the code"""

        self.display.show()
        # self.maybe_gc()

    def draw_sprites(self):
        for my_sprite in self.instances:
            my_sprite.show(self.display)


    def maybe_gc(self):
        now = utime.ticks_ms()
        if self.gc_interval and ((now - self.last_gc) > self.gc_interval):
            gc.collect()
            self.last_gc = utime.ticks_ms()

    @staticmethod
    def check_mem():
        gc.collect()
        print(f"Free memory: {gc.mem_free():,} bytes")
        print(micropython.mem_info())

    @staticmethod
    def mem_marker(msg=None):
        gc.collect()
        print(msg)
        print(micropython.mem_info())

ScreenBounds = namedtuple(
    "ScreenBounds",
    (
        "left",
        "right",
        "top",
        "bottom",
    )
)