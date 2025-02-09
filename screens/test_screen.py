import _thread
import gc

import time
import math
import random

from uctypes import addressof

import input_rotary

from scaler.sprite_scaler import SpriteScaler
from screens.test_screen_base import TestScreenBase
from sprites2.sprite_physics import SpritePhysics
from sprites2.test_pyramid import TestPyramid

from sprites2.test_square import TestSquare
from sprites2.test_heart import TestHeart
from sprites2.test_grid import TestGrid
from sprites2.sprite_manager_2d import SpriteManager2D

from sprites2.sprite_types import SPRITE_TEST_SQUARE, SPRITE_TEST_HEART, SPRITE_TEST_GRID, SPRITE_TEST_GRID_SPEED, \
    SpriteType, SPRITE_TEST_PYRAMID

from profiler import Profiler as prof

import utime
import uasyncio as asyncio

from perspective_camera import PerspectiveCamera
from colors import color_util as colors
from colors import framebuffer_palette as fp

FramebufferPalette = fp.FramebufferPalette
import framebuf as fb

BLACK = 0x000000
CYAN =  0x00FFFF
GREEN = 0x00FF00
GREY =  0x444444
YELLOW = 0xFFFF00
WHITE = 0xFFFFFF

class TestScreen(TestScreenBase):
    debug = False
    debug_inst = False
    fps_enabled = True
    fps_counter_task = None
    color_idx = 0
    color_len = 0
    color_demo = False

    screen_width = 96
    screen_height = 64
    scale_id = 0
    scale_source = None
    scale_source_len = 0
    scales = []
    scaler = None
    scaled_width = 0
    scaled_height = 0
    score = 0
    sprite_palette = None

    base_speed = 1 / 800
    base_x = 0
    base_y = 0
    delta_y = 2
    delta_x = 2
    draw_y_dir = 1
    draw_x_dir = -1
    draw_y = 0
    draw_x = 0
    slide_sel = 'vert'
    h_scale = 1
    v_scale = 1
    refresh_method = None
    num_sprites = 40
    max_sprites = 0
    scaler_num_sprites = 1
    sprite_max_z = 1000
    display_task = None

    last_perf_dump_ms = None
    instances = []
    lines = []
    # line_color = colors.hex_to_rgb(0xFFFFFF)
    line_colors = [ colors.hex_to_565(0xFF0000),
                    colors.hex_to_565(0x00FF00),
                    colors.hex_to_565(0x0000FF)]

    rainbow_colors = [
        0xFF0000,  # Red
        0xFF7F00,  # Orange
        0xFFFF00,  # Yellow
        0x7FFF00,  # Chartreuse
        0x00FF00,  # Green
        0x00FF7F,  # Spring Green
        0x00FFFF,  # Cyan
        0x0000FF,  # Blue
        0x7F00FF,  # Purple
        0xFF00FF,  # Magenta
    ]

    mgr = None

    sprite = None # SpriteType (not instance)
    inst = None
    image = None
    num_cols = None
    num_rows = None
    sep = 2
    sep_dir = 1
    bg_color = colors.hex_to_565(GREY)
    x_offset = 0
    y_offset = 0
    all_coords = [] # list of x/y tuples

    def __init__(self, display, *args, **kwargs):
        super().__init__(display)
        print()
        print(f"=== Testing performance of {self.num_sprites} sprites ===")
        print()

        self.idx = 0

        self.sprite_id = None
        print(f"Free memory __init__: {gc.mem_free():,} bytes")

        # self.x_vals = [(0*i) for i in range(num_sprites)]
        # self.y_vals = [(0*i) for i in range(num_sprites)]
        # self.y_vals = [(random.randrange(-30, 30)) for _ in range(num_sprites)]

        self.sprite_scales = [random.choice(range(0, 9)) for _ in range(self.num_sprites)]

        self.init_camera()
        self.create_lines()

        self.scaler = SpriteScaler(self.display)
        self.scaler.prof = prof

        # self.actions = actions = self.mgr.sprite_actions
        # self.actions.add_action(SPRITE_TEST_HEART, actions.check_bounds_and_remove)

        self.all_scales = self.scaler.dma.patterns.get_horiz_patterns()
        self.all_keys = self.all_scales.keys()

        self.one_scales = {scale: patt for scale, patt in self.all_scales.items() if scale <= 1}
        self.two_scales = {scale: patt for scale, patt in self.all_scales.items() if scale <= 3 and scale >= 0.1}

        self.grid_beat = False
        self.fallout = False
        self.speed_vectors = []

    def create_sprite_manager(self, num_sprites=0):
        self.check_mem()
        print("-- Creating Sprite Manager...")
        self.max_sprites = num_sprites
        self.mgr = SpriteManager2D(self.display, self.max_sprites, self.camera)
        return self.mgr

    def run(self):
        self.running = True
        self.init_common()
        self.load_types()

        test = 'scale_control'
        self.check_mem()
        method = None

        if test == 'zoom_heart':
            self.sprite_id = SPRITE_TEST_HEART
            self.load_sprite(SPRITE_TEST_HEART)
            self.init_beating_heart()
            method = self.do_refresh_zoom_in
        elif test == 'zoom_sq':
            self.sprite_id = SPRITE_TEST_SQUARE
            self.load_sprite(SPRITE_TEST_SQUARE)
            self.init_beating_heart()
            method = self.do_refresh_zoom_in
        if test == 'scale_control':
            self.sprite_id = SPRITE_TEST_PYRAMID
            self.load_sprite(SPRITE_TEST_PYRAMID)
            self.init_score()
            self.init_scale_control()
            method = self.do_refresh_scale_control
        elif test == 'grid1':
            self.grid_beat = False
            self.fallout = False
            self.color_demo = False

            self.sprite_id = SPRITE_TEST_HEART
            self.load_sprite(SPRITE_TEST_HEART)
            self.init_grid()
            method = self.do_refresh_grid
        elif test == 'grid2':
            self.sprite_id = SPRITE_TEST_SQUARE
            self.load_sprite(SPRITE_TEST_SQUARE)
            self.init_grid()
            self.grid_beat = False
            self.fallout = True
            method = self.do_refresh_grid
        elif test == 'grid3':
            self.sprite_id = SPRITE_TEST_GRID
            self.load_sprite(SPRITE_TEST_GRID)
            self.init_grid()
            method = self.do_refresh_grid
        elif test == 'square':
            self.sprite_id = SPRITE_TEST_SQUARE
            self.init_common(1)
            self.load_sprite(SPRITE_TEST_SQUARE)
            self.init_clipping_square()
            method = self.do_refresh_clipping_square
        else:
            raise Exception(f"Invalid method: {method}")

        self.refresh_method = getattr(self, method.__name__, None)

        self.check_mem()

        loop = asyncio.get_event_loop()
        loop.create_task(self.start_display_loop())

        if self.fps_enabled:
            self.fps_counter_task = asyncio.create_task(self.start_fps_counter())

        asyncio.run(self.start_main_loop())

    async def start_main_loop(self):
        print("-- ... MAIN LOOP STARTING ...")
        self.check_mem()

        """ All top level tasks / threads go here. Once all of these finish, the program ends"""
        await asyncio.gather(
            self.update_loop(),
        )

    async def update_loop(self):
        start_time_ms = self.last_update_ms = utime.ticks_ms()
        self.last_perf_dump_ms = start_time_ms

        print(f" == CPU CORE {_thread.get_ident()} (update_loop) ==")

        # update loop - will run until task cancellation
        try:
            while True:
                last_update_ms = now = utime.ticks_ms()
                elapsed = utime.ticks_diff(now, self.last_update_ms)
                if elapsed:
                    self.mgr.update(elapsed)
                    self.last_update_ms = last_update_ms

                # Tweaking this number can give FPS gains / give more frames to `elapsed`, avoiding near zero
                # errors
                await asyncio.sleep_ms(10)

        except asyncio.CancelledError:
            return False

    def get_elapsed(self):
        return utime.ticks_ms() - self.last_tick

    def init_common(self, num_sprites=1):
        self.max_sprites = num_sprites
        self.mgr = self.create_sprite_manager(num_sprites)

    def init_grid(self):
        # meta = self.mgr.get_meta(self.sprite)
        self.inst, idx = self.mgr.pool.get(self.sprite_id, self.sprite)

        sprite_width = self.sprite.width
        sprite_height = self.sprite.height
        self.image = self.mgr.sprite_images[self.sprite_id][-1]

        print(f"RIGHT NOW IMAGE.palette is: {addressof(self.image.palette.palette)}")

        one_scales1 = list(self.one_scales.keys())
        one_scales1_rev = one_scales1.copy()
        one_scales1_rev.reverse()

        one_scales2 = one_scales1.copy()
        one_scales2.reverse()
        self.plus_one_scale_keys = one_scales2 + one_scales1

        times = 2
        self.one_two_scale_keys = [1] * times + list(self.two_scales.keys()) + [1] * times
        self.one_scale_keys = [1] * times + one_scales1_rev + [1] * times

        max_cols = 12
        max_rows = 10
        # max_cols = max_rows = 1

        self.num_cols = min(self.screen_width // 16, max_cols)
        self.num_rows = min(self.screen_height // 16, max_rows)

        h_scale = v_scale = 1
        self.scaled_width = int(sprite_width * h_scale)
        self.scaled_height = int(sprite_height * v_scale)

        if self.fallout:
            self.scale_source = self.one_scale_keys
        else:
            self.scale_source = self.one_two_scale_keys

        if self.grid_beat or self.fallout:
            self.scale_source = list(self.scale_source)
            self.scale_source_len = len(self.scale_source)

        if self.color_demo:
            self.color_len = len(self.rainbow_colors)

        """ Precache x/y (scale 1 only) """
        row_sep = sprite_width - 1
        col_sep = sprite_width

        all_coords = []

        for c in range(self.num_cols):
            for r in range(self.num_rows):
                draw_x = int(c * col_sep)
                draw_y = int(r * row_sep)
                all_coords.append([draw_x, draw_y])

        self.all_coords = all_coords

    async def start_display_loop(self):
        while True:
            self.refresh_method()
            await asyncio.sleep_ms(1)

    def init_beating_heart(self):
        # self.sprite = self.mgr.get_meta(self.sprite)
        self.image = self.mgr.sprite_images[self.sprite_id][-1]

        h_scales1 = list(self.all_scales.keys())
        h_scales1.sort()

        """ Double up the scale """
        h_scales2 = h_scales1.copy()
        h_scales2.reverse()

        self.h_scales = h_scales1

    def init_scale_control(self):
        # self.sprite = self.mgr.get_meta(self.sprite)
        self.init_fps()
        self.inst, idx = self.mgr.pool.get(self.sprite_id, self.sprite)

        self.draw_x = self.display.width // 2
        self.draw_y = self.display.height // 2
        self.image = self.mgr.sprite_images[self.sprite_id][-1]


        # init 4bit palette
        for i in range(16):
            if i == 0:
                self.score_palette.set_bytes(i, 0)
            elif i == 1:
                self.score_palette.set_bytes(i, WHITE)
            else:
                self.score_palette.set_bytes(i, WHITE)

        self.h_scales = list(self.all_scales.keys())
        self.h_scales.sort()

        default = 1
        self.scale_id = self.h_scales.index(default)

        self.input_handler = input_rotary.InputRotary()
        self.input_handler.handler_right = self.scale_control_right
        self.input_handler.handler_left = self.scale_control_left

        loop = asyncio.get_event_loop()
        self.update_score_task = loop.create_task(self.update_score())

    def scale_control_right(self):
        if self.scale_id < len(self.h_scales)-1:
            self.scale_id += 1
            if self.debug:
                scale = self.h_scales[self.scale_id]
                self.sprite.scale = scale
                print(f"S: {scale:.03f}")

    def scale_control_left(self):
        if self.scale_id > 0:
            self.scale_id -= 1
            if self.debug:
                scale = self.h_scales[self.scale_id]
                self.sprite.scale = scale
                print(f"S: {scale:.03f}")

    def init_clipping_square(self):
        # self.sprite = self.mgr.get_meta(self.sprite)
        self.image = self.mgr.sprite_images[self.sprite_id][-1]
        self.curr_dir = 'horiz'
        self.bounce_count = 0

        self.h_scale = self.v_scale = 4
        self.scaled_width = math.ceil(self.sprite.width * self.h_scale)
        self.scaled_height = math.ceil(self.sprite.height * self.v_scale)

        loop = asyncio.get_event_loop()
        loop.create_task(self.flip_dir())

    def do_refresh_grid(self):
        """
        Show a grid of heart Sprites
        """
        prof.start_profile('scaler.draw_loop_init')
        row_sep = self.sprite.width
        col_sep = self.sprite.width

        self.common_bg()

        prof.end_profile('scaler.draw_loop_init')

        self.idx = 0

        inst = self.inst

        color_demo = self.color_demo

        for c in range(self.num_cols):
            for r in range(self.num_rows):
                prof.start_profile('scaler.pre_draw')

                inst.draw_x = c * col_sep
                inst.draw_y = r * row_sep

                if False or self.grid_beat or self.fallout:
                    scale_factor = (self.scale_id+self.idx) % self.scale_source_len
                    self.scale_id += 1
                    self.h_scale = self.scale_source[scale_factor]
                    self.v_scale = self.h_scale

                    self.scaled_width = self.sprite.height * self.h_scale
                    self.scaled_height = self.sprite.height * self.v_scale

                    # draw_x, draw_y = self.scaler.center_sprite(self.scaled_width, self.scaled_height)
                prof.end_profile('scaler.pre_draw')

                self.scaler.draw_sprite(
                    self.sprite,
                    inst,
                    self.image,
                    h_scale=self.h_scale,
                    v_scale=self.v_scale)

                self.idx = self.idx + 1

                if color_demo:
                    new_color = self.rainbow_colors[self.color_idx % self.color_len]
                    self.sprite_palette.set_hex(3, new_color)
                    self.color_idx += 1

        prof.start_profile('scaler.display_show')

        while not self.scaler.dma.read_finished:
            pass

        self.display.show()
        prof.end_profile('scaler.display_show')

        self.show_prof()
        self.fps.tick()

    def do_refresh_zoom_in(self):
        """
        Do a zoom in demo of increasingly higher scale ratios
        """

        h_scale = self.h_scales[self.scale_id % len(self.h_scales)]
        v_scale = h_scale

        sprite_scaled_width = self.sprite.width * h_scale
        sprite_scaled_height = self.sprite.height * v_scale

        display_width = self.display.width
        display_height = self.display.height

        draw_x = (display_width / 2) - (sprite_scaled_width / 2)
        draw_y = (display_height / 2) - (sprite_scaled_height / 2)

        if self.scaler.debug:
            print("IN SCREEN about to draw_sprite:")
            print(f"  v_scale: {v_scale}")
            print(f"  h_scale: {h_scale}")
            print(f"  fbuff_width: {self.scaler.framebuf.frame_width}")
            print(f"  fbuff_height: {self.scaler.framebuf.frame_height}")
            print(f"  draw_x: {draw_x}")
            print(f"  draw_y: {draw_y}")
            print(f"  sprite_scaled_width: {sprite_scaled_width}")
            print(f"  sprite_scaled_height: {sprite_scaled_height}")

        self.display.fill(0x000000)
        self.scaler.draw_sprite(
            self.sprite,
            self.inst,
            self.image,
            h_scale=h_scale,
            v_scale=v_scale)

        self.scale_id += 1
        self.show_prof()
        self.display.swap_buffers()

        time.sleep_ms(50)
        self.fps.tick()

    def do_refresh_scale_control(self):
        """
        Do a zoom in demo of increasingly higher scale ratios
        """

        h_scale = self.h_scales[self.scale_id]
        self.sprite.scale = v_scale = h_scale
        # self.sprite.scale = v_scale = h_scale = 3.750
        # self.sprite.scale = v_scale = h_scale = 3

        scaled_width = scaled_height = int(h_scale * self.sprite.height)
        self.inst.x, self.inst.y = 48, 32
        self.inst.draw_x, self.inst.draw_y = SpritePhysics.get_draw_pos(self.inst, scaled_width=scaled_width, scaled_height=scaled_height)
        self.common_bg()
        self.scaler.draw_sprite(
            self.sprite,
            self.inst,
            self.image,
            h_scale=h_scale,
            v_scale=v_scale)

        # self.score_text.render_text(f"{self.score:09}")
        # print(f"PRINTING SCALE: {h_scale}")
        self.score_text.render_text(f"{h_scale:.3f}")
        self.score_text.show(self.display.write_framebuf, self.score_palette)

        self.display.show()

        self.show_prof()
        time.sleep_ms(1)
        self.fps.tick()

    def do_refresh_clipping_square(self):
        """
        Do a demo of several diverse horizontal scale ratios
        """
        self.h_scales = [2]

        x_max = 96
        x_min = 0 - self.scaled_width

        y_max = 64
        y_min = 0 - self.scaled_height


        if self.slide_sel == 'horiz':
            """ Modify draw_x over time"""
            if self.draw_x > x_max:
                self.draw_x_dir = -1
            elif self.draw_x < x_min:
                self.draw_x_dir = +1
            self.draw_x += self.delta_x * self.draw_x_dir

        elif self.slide_sel == 'vert':
            """ Modify draw_y over time"""
            if self.draw_y > y_max:
                self.draw_y_dir = -1
            elif self.draw_y < y_min:
                self.draw_y_dir = +1
            self.draw_y += self.delta_y * self.draw_y_dir

        self.display.fill(0x000000)
        self.scaler.draw_sprite(
            self.sprite,
            self.inst,
            self.image,
            h_scale=self.h_scale,
            v_scale=self.v_scale)

        self.scale_id += 1
        self.show_prof()
        # loop = asyncio.get_event_loop()
        # loop.create_task(self.display.swap_buffers())
        self.display.swap_buffers()
        # time.sleep_ms(10)
        self.fps.tick()


    async def flip_dir(self):
        while True:
            if self.slide_sel == 'horiz':
                self.slide_sel = 'vert'
            else:
                self.slide_sel = 'horiz'
            await asyncio.sleep_ms(2000)

    def do_refresh(self):
        return self.refresh_method()

    def create_lines(self):
        count = 64
        self.lines = []

        for i in range(count):
            y_start = 16 + int(i)
            y_start -= y_start % 2
            idx = math.floor(random.randrange(0,3))
            color = self.line_colors[idx]
            self.lines.append([int(0), int(y_start-16), int(95), int(y_start), color])

    async def sprite_fps_test(self):
        # self.create_sprites()
        self.last_tick = utime.ticks_ms()

        while True:
            self.sprite_fps_test_func()
            await asyncio.sleep(1 / 100)

    def show_prof(self):
        interval = 5000  # Every 5 secs

        now = utime.ticks_ms()
        delta = utime.ticks_diff(now, self.last_perf_dump_ms)
        if delta > interval:
            prof.dump_profile('scaler')
            self.last_perf_dump_ms = utime.ticks_ms()

    def sprite_fps_test_func(self):
        elapsed = utime.ticks_ms() - self.last_tick

        for i, sprite in enumerate(self.instances):
            sprite.z = sprite.z + 6
            sprite.update(elapsed)
            # print(f"z: {sprite.z}")
        self.last_tick = utime.ticks_ms()

    # async def display_line_test(self):
    #     while True:
    #         self.mgr.update(0)
    #         await asyncio.sleep(1 / 60)

    def load_sprite(self, sprite_type):
        """ Creates images if not exist, returns meta"""
        self.sprite = self.mgr.sprite_metadata[sprite_type]
        self.sprite_palette = self.mgr.get_palette(sprite_type)
        self.sprite_img = self.mgr.sprite_images[sprite_type]

        return self.sprite

    def load_types(self):
        self.mgr.add_type(
            sprite_type=SPRITE_TEST_HEART,
            sprite_class=TestHeart)

        self.mgr.add_type(
            sprite_type=SPRITE_TEST_SQUARE,
            sprite_class=TestSquare)

        self.mgr.add_type(
            sprite_type=SPRITE_TEST_GRID,
            sprite_class=TestGrid)

        self.mgr.add_type(
            sprite_type=SPRITE_TEST_PYRAMID,
            sprite_class=TestPyramid)

    def init_camera(self):
        # Camera
        horiz_y: int = 16
        pos_y = 50
        max_sprite_height = -6

        self.camera = PerspectiveCamera(
            self.display,
            pos_x=0,
            pos_y=pos_y,
            pos_z=-int(pos_y / 2),
            vp_x=0,
            vp_y=horiz_y,
            min_y=horiz_y + 4,
            max_y=self.display.height + max_sprite_height,
            fov=90.0)


    def show_lines(self):
        for line in self.lines:
            # print(f"Line in {line[0]},{line[1]}, / {line[2]},{line[3]}")
            x1 = line[0]
            y1 = line[1]
            x2 = line[2]
            y2 = line[3]
            color = line[4]

            y2 = y2 + int(random.randrange(0, 2))
            self.display.hline(x1, y1, self.camera.screen_width, color)

    def make_exp_list(self, nums, base=2, min_copies=1, max_total=256):
        result = []
        length = len(nums)

        # Calculate total slots needed to avoid overallocation
        total_slots = min(max_total, sum(int(base ** (length - i - 1)) for i in range(length)))

        for i, num in enumerate(nums):
            # Calculate count for this number
            power = min(length - i - 1, 4)  # Cap power at 4 to avoid huge numbers
            count = int(base ** power)
            count = min(count, total_slots - len(result))  # Respect max slots
            count = max(min_copies, count)  # Respect min copies

            if count > 0:
                result.extend([num] * count)

            if len(result) >= total_slots:
                break

        return result
