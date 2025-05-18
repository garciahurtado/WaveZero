import gc

import utime
import uasyncio as asyncio
from ucollections import namedtuple

from fps_counter import FpsCounter
from scaler.const import INK_BRIGHT_YELLOW
from scaler.scaler_debugger import printc
from sprites_old.sprite import Sprite
import micropython
from ssd1331_pio import SSD1331PIO

PixelBounds = namedtuple(
    "PixelBounds",
    (
        "left",
        "right",
        "top",
        "bottom",
    )
)

class Screen:
    debug = True
    display = None
    bounds = None
    margin_px = 0
    instances: [Sprite]
    last_gc: int = 0
    gc_interval: int = 3000 # how often to call the garbage collector (ms)
    # gc_interval = 0
    app: None # ref. to ScreenApp
    fps = None
    total_width = 0
    total_height = 0
    half_height = 0
    half_width = 0

    def __init__(self, display:SSD1331PIO=None, margin_px=0):

        self.instances = []
        if display:
            self.display = display
            self.bounds = PixelBounds(
                left = 0-margin_px,
                right= display.WIDTH + margin_px,
                top = 0-margin_px,
                bottom= display.HEIGHT + margin_px
            )
            self.half_height = display.height // 2
            self.half_width = display.width // 2

        self.margin_px = margin_px
        margin = self.margin_px
        display = self.display
        self.total_width = display.WIDTH + 2*margin  # Add margin on both sides
        self.total_height = display.HEIGHT + 2*margin

        self.fps = FpsCounter()
        self.last_gc = utime.ticks_ms()

    def run(self):
        raise RuntimeError("* screen.run() not implemented! *")

    async def start_display_loop(self):
        print("** DISPLAY LOOP START (screen.py) **")

        while True:
            self.do_refresh()
            await asyncio.sleep_ms(1)

    async def start_main_loop(self):
        print("<< UPDATE LOOP START (screen.py) >>")
        await asyncio.gather(
            self.update_loop(),
        )

    async def start_fps_counter(self, pool=None):
        await asyncio.sleep(5)  # wait for things to stabilize before measuring FPS

        while True:
            fps = self.fps.fps()
            if not fps or not pool:
                pass
            else:
                fps_str = "{: >6.2f}".format(fps)
                extra_text = pool.active_count
                printc(f"FPS: {fps_str} // {extra_text:03.} SPRITES", INK_BRIGHT_YELLOW)

                # # ColorWriter.set_textpos(self.display.write_framebuf, 0, 0)
                # self.fps_text.row_clip = True
                # self.fps_text.render_text(fps_str)

            await asyncio.sleep(1)

    def do_refresh(self):
        """ Meant to be overridden in child classes """
        self.display.show()
        # self.maybe_gc()

    def draw_sprites(self):
        for my_sprite in self.instances:
            my_sprite.show(self.display)

    def add_sprite(self, sprite):
        """ Adds a 'fat sprite' to the list of sprites to render at the screen level (background, player, score,
        anything static or permanent """
        self.instances.append(sprite)

    def is_sprite_in_bounds(self, sprite_bounds: PixelBounds, screen_bounds=None):
        if not screen_bounds:
            screen_bounds = self.bounds

        if (screen_bounds.left <= sprite_bounds.left <= screen_bounds.right) and \
           (screen_bounds.left <= sprite_bounds.right <= screen_bounds.right) and \
           (screen_bounds.top <= sprite_bounds.top <= screen_bounds.bottom) and \
           (screen_bounds.top <= sprite_bounds.bottom <= screen_bounds.bottom):
            return True

        # Otherwise its out of bounds
        return False

    def is_point_in_bounds(self, point, screen_bounds=None):
        if not screen_bounds:
            screen_bounds = self.bounds

        point_x, point_y = point

        if (screen_bounds.left <= point_x <= screen_bounds.right) and \
           (screen_bounds.top <= point_y <= screen_bounds.bottom):
            return True

        # Otherwise its out of bounds
        return False


    def maybe_gc(self):
        now = utime.ticks_ms()
        if self.gc_interval and ((now - self.last_gc) > self.gc_interval):
            gc.collect()
            self.last_gc = utime.ticks_ms()

    @staticmethod
    def check_gc_mem(collect=False):
        if collect:
            gc.collect()
        print(f"Free memory: {gc.mem_free():,} bytes")
        print(micropython.mem_info())

    @staticmethod
    def mem_marker(msg=None):
        gc.collect()
        print(msg)
        print(micropython.mem_info())
