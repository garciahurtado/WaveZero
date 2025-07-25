import gc

import utime
import uasyncio as asyncio
from ucollections import namedtuple

from fps_counter import FpsCounter
from profiler import prof, timed
from scaler.const import INK_BRIGHT_YELLOW, DEBUG_FPS, DEBUG_FRAME_ID
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
    last_perf_dump_ms = 0
    total_frames = 0

    # This will be set to True by the render loop when it finishes (then the game world is ready to be updated)
    is_render_finished = False

    # this will be set to True by the update loop when it finishes (then the display is ready to be rendered)
    is_update_finished = False

    def __init__(self, display:SSD1331PIO=None, margin_px=16):
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

    async def start_render_loop(self):
        """ The main display loop. """

        while True:
            if self.is_update_finished:
                self.do_render()
                self.is_render_finished = True
            else:
                # wait for the update loop to catch up
                await asyncio.sleep(1/30)

            if DEBUG_FPS:
                self.fps.tick()

            if DEBUG_FRAME_ID:
                self.total_frames += 1

            # Pause to ensure we don't try to render faster than the display can handle
            # but also to free up the event loop for other tasks
            await asyncio.sleep_ms(1)

    async def start_update_loop(self):
        print("<< UPDATE LOOP START (screen.py) >>")
        await asyncio.gather(
            self.update_loop(),
        )

    async def update_loop(self):
        start_time_ms = self.last_update_ms = utime.ticks_ms()
        self.last_perf_dump_ms = start_time_ms

        print(f"--- ({self.__class__.__name__}) Update loop Start time: {start_time_ms}ms ---")

        # update loop - will run until task cancellation
        try:
            while True:
                if self.is_render_finished:
                    self.do_update()
                    self.is_update_finished = True
                else:
                    # give the display some time to catch up
                    await asyncio.sleep(1/30)

                await asyncio.sleep(1/60)   # Tweaking this number can improve FPS

        except asyncio.CancelledError:
            return False

    async def start_fps_counter(self, pool=None):
        await asyncio.sleep(5)          # wait for a few seconds before starting to measure FPS

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

            await asyncio.sleep(1)      # Update every second

    def do_render(self):
        """ Meant to be overridden in child classes """
        # self.maybe_gc()

    def draw_sprites(self):
        """ Meant to be overridden in child classes """
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

    async def update_profiler(self):
        while True:
            await asyncio.sleep(5)
            prof.dump_profile()

    def update_profiler_sync(self):
        """Synchronous version of the profiler update method."""
        interval = 5000  # Every 5 secs

        now = utime.ticks_ms()
        delta = utime.ticks_diff(now, self.last_perf_dump_ms)
        if delta > interval:
            prof.dump_profile()
            self.last_perf_dump_ms = utime.ticks_ms()

    @staticmethod
    def mem_marker(msg=None):
        gc.collect()
        print(msg)
        print(micropython.mem_info())
