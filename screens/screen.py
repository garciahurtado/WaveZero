import gc
import time

import utime
import uasyncio as asyncio
from ucollections import namedtuple

from fps_counter import FpsCounter
from sprites.sprite import Sprite
import micropython

class Screen:
    display = None
    bounds = None
    margin_px = 8
    instances: [Sprite]
    last_tick: int = 0
    last_gc: int = 0
    gc_interval: int = 3000 # how often to call the garbage collector (ms)
    app: None # ref to ScreenApp
    profile_labels = {}
    display_loop_wait = 2 # ms for the display loop to wait between refreshes
    fps = 0
    target_fps = 30

    def __init__(self, display=None):
        self.instances = []
        if display:
            self.display = display
            self.bounds = ScreenBounds(
                left = -self.margin_px,
                right= display.width + self.margin_px,
                top = -self.margin_px,
                bottom= display.height + self.margin_px
            )
        self.fps = FpsCounter()

    def add(self, sprite):
        self.instances.append(sprite)

    async def refresh_display(self):
        wait_s = 1/30# max FPS
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
        # self.last_tick = self.fps.tick()

        # display_loop_wait = self.display_loop_wait
        # step = 10
        # if self.fps > self.target_fps:
        #     display_loop_wait += step
        #     if display_loop_wait > 60:
        #         display_loop_wait = 60
        # elif self.fps < self.target_fps:
        #     display_loop_wait -= step
        #     if display_loop_wait < 1:
        #         display_loop_wait = 1
        #
        # self.display_loop_wait = display_loop_wait

        self.display.show()

    def draw_sprites(self):
        for my_sprite in self.instances:
            my_sprite.show(self.display)

    def is_within_bounds(self, coords, sprite):
        x, y = coords.x, coords.y
        center_x = int(x + (sprite.width/2))
        center_y = int(y + (sprite.height/2))
        bounds = self.bounds

        if ((center_x > bounds.left) and \
             (center_x < bounds.right) and \
              (center_y > bounds.top) and \
               (center_y < bounds.bottom)):
            return True

        return False


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