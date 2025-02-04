import _thread
import gc

import time
import math
import random

import input_rotary

from scaler.sprite_scaler import SpriteScaler
from screens.screen import Screen
from sprites.sprite import Sprite

from sprites2.test_square import TestSquare
from sprites2.test_heart import TestHeart
from sprites2.test_grid import TestGrid
from sprites2.sprite_manager_2d import SpriteManager2D

from sprites2.sprite_types import SPRITE_TEST_SQUARE, SPRITE_TEST_HEART, SPRITE_TEST_GRID, SPRITE_TEST_GRID_SPEED

from profiler import Profiler as prof
from images.image_loader import ImageLoader
import fonts.vtks_blocketo_6px as font_vtks
from font_writer_new import ColorWriter

import utime
import uasyncio as asyncio

from perspective_camera import PerspectiveCamera
from color import color_util as colors
from color.framebuffer_palette import FramebufferPalette
import framebuf as fb

CYAN =  0x00FFFF
GREEN = 0x00FF00
BLACK = 0x000000
GREY =  0x444444

prof.enabled = False

class TestScreen(Screen):
    debug = False
    debug_inst = False
    fps_enabled = True
    fps_counter_task = None
    grid_center = False
    grid_lines = False

    screen_width = 96
    screen_height = 64
    scale_id = 0
    scale_source = None
    scale_source_len = 0
    scales = []
    scaler = None
    scaled_width = 0
    scaled_height = 0

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
    current_loop = None
    num_sprites = 40
    max_sprites = 0
    scaler_num_sprites = 1
    sprite_max_z = 1000
    display_task = None
    grid_color = colors.hex_to_565(0x00FF00)
    grid_lines_color = colors.hex_to_565(0x0b2902)

    last_perf_dump_ms = None
    fps_text: ColorWriter
    instances = []
    lines = []
    # line_color = colors.hex_to_rgb(0xFFFFFF)
    line_colors = [ colors.hex_to_565(0xFF0000),
                    colors.hex_to_565(0x00FF00),
                    colors.hex_to_565(0x0000FF)]
    score_palette = FramebufferPalette(16, color_mode=fb.GS4_HMSB)
    mgr = None

    sprite = None # SpriteType (not instance)
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

        self.sprite_type = None
        # self.preload_images()

        print(f"Free memory __init__: {gc.mem_free():,} bytes")

        # self.x_vals = [(0*i) for i in range(num_sprites)]
        # self.y_vals = [(0*i) for i in range(num_sprites)]
        # self.y_vals = [(random.randrange(-30, 30)) for _ in range(num_sprites)]

        self.sprite_scales = [random.choice(range(0, 9)) for _ in range(self.num_sprites)]

        self.init_camera()
        # self.init_fps()
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

        test = 'grid1'
        self.check_mem()
        method = None

        if test == 'zoom_heart':
            self.sprite_type = SPRITE_TEST_HEART
            self.load_sprite(SPRITE_TEST_HEART)
            self.init_beating_heart()
            method = self.do_refresh_zoom_in
        elif test == 'zoom_sq':
            self.sprite_type = SPRITE_TEST_SQUARE
            self.load_sprite(SPRITE_TEST_SQUARE)
            self.init_beating_heart()
            method = self.do_refresh_zoom_in
        if test == 'scale_control':
            self.sprite_type = SPRITE_TEST_HEART
            self.load_sprite(SPRITE_TEST_HEART)
            self.init_scale_control()
            method = self.do_refresh_scale_control
        elif test == 'grid1':
            self.sprite_type = SPRITE_TEST_HEART
            self.load_sprite(SPRITE_TEST_HEART)
            self.init_grid()
            self.grid_beat = False
            self.fallout = False
            method = self.do_refresh_grid
        elif test == 'grid2':
            self.sprite_type = SPRITE_TEST_SQUARE
            self.load_sprite(SPRITE_TEST_SQUARE)
            self.init_grid()
            self.grid_beat = False
            self.fallout = True
            method = self.do_refresh_grid
        elif test == 'grid3':
            self.sprite_type = SPRITE_TEST_GRID
            self.load_sprite(SPRITE_TEST_GRID)
            self.init_grid()
            method = self.do_refresh_grid
        elif test == 'square':
            self.sprite_type = SPRITE_TEST_SQUARE
            self.init_common(1)
            self.load_sprite(SPRITE_TEST_SQUARE)
            self.init_clipping_square()
            method = self.do_refresh_clipping_square
        else:
            raise Exception(f"Invalid method: {method}")

        self.current_loop = getattr(self, method.__name__, None)

        self.check_mem()

        loop = asyncio.get_event_loop()
        loop.create_task(self.start_display_loop())

        if self.fps_enabled:
            self.fps_counter_task = asyncio.create_task(self.start_fps_counter())

        asyncio.run(self.start_main_loop())

    def preload_images(self):
        images = [
            # {"name": "bike_sprite.bmp", "width": 32, "height": 22, "color_depth": 4},
            # {"name": "laser_wall.bmp", "width": 24, "height": 10, "color_depth": 4},
            # {"name": "laser_orb_grey.bmp", "width": 16, "height": 16, "color_depth": 4},
        ]

        ImageLoader.load_images(images, self.display)

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
                self.last_update_ms = now = utime.ticks_ms()
                elapsed = utime.ticks_diff(now, self.last_update_ms) + 1

                self.mgr.update(elapsed)

                # Tweaking this number can give FPS gains / give more frames to `elapsed`, avoiding near zero
                # errors
                await asyncio.sleep(1)

        except asyncio.CancelledError:
            return False

    def get_elapsed(self):
        return utime.ticks_ms() - self.last_tick

    def init_common(self, num_sprites=1):
        self.max_sprites = num_sprites
        self.mgr = self.create_sprite_manager(num_sprites)

    def init_grid(self):
        # self.sprite = self.mgr.get_meta(self.sprite)
        sprite_width = self.sprite.width
        sprite_height = self.sprite.height
        self.image = self.mgr.sprite_images[self.sprite_type][-1]

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
            self.do_refresh_grid()
            await asyncio.sleep_ms(1)

    def init_beating_heart(self):
        # self.sprite = self.mgr.get_meta(self.sprite)
        self.image = self.mgr.sprite_images[self.sprite_type][-1]

        h_scales1 = list(self.all_scales.keys())
        h_scales1.sort()

        """ Double up the scale """
        h_scales2 = h_scales1.copy()
        h_scales2.reverse()

        self.h_scales = h_scales1

    def init_scale_control(self):
        # self.sprite = self.mgr.get_meta(self.sprite)
        self.image = self.mgr.sprite_images[self.sprite_type][-1]

        self.h_scales = list(self.all_scales.keys())
        self.h_scales.sort()

        default = 3.750
        self.scale_id = self.h_scales.index(default)

        self.input_handler = input_rotary.InputRotary()
        self.input_handler.handler_right = self.scale_control_right
        self.input_handler.handler_left = self.scale_control_left

    def scale_control_right(self):
        if self.scale_id < len(self.h_scales)-1:
            self.scale_id += 1
            if self.debug:
                scale = self.h_scales[self.scale_id]
                print(f"S: {scale:.03f}")

    def scale_control_left(self):
        if self.scale_id > 0:
            self.scale_id -= 1
            if self.debug:
                scale = self.h_scales[self.scale_id]
                print(f"S: {scale:.03f}")

    def init_clipping_square(self):
        # self.sprite = self.mgr.get_meta(self.sprite)
        self.image = self.mgr.sprite_images[self.sprite_type][-1]
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
        idx = 0
        row_sep = self.sprite.width
        col_sep = self.sprite.width

        self.common_bg()

        prof.end_profile('scaler.draw_loop_init')

        for c in range(self.num_cols):
            for r in range(self.num_rows):
                prof.start_profile('scaler.pre_draw')

                draw_x = int(c * col_sep)
                draw_y = int(r * row_sep)

                if False or self.grid_beat or self.fallout:
                    scale_factor = (self.scale_id+idx) % self.scale_source_len
                    self.scale_id += 1
                    self.h_scale = self.scale_source[scale_factor]
                    self.v_scale = self.h_scale

                    self.scaled_width = self.sprite.height * self.h_scale
                    self.scaled_height = self.sprite.height * self.v_scale

                    draw_x, draw_y = self.scaler.center_sprite(self.scaled_width, self.scaled_height)
                prof.end_profile('scaler.pre_draw')

                prof.start_profile('scaler.draw_sprite')
                self.scaler.draw_sprite(
                    self.sprite,
                    int(draw_x),
                    int(draw_y),
                    self.image,
                    h_scale=self.h_scale,
                    v_scale=self.v_scale)
                prof.end_profile('scaler.draw_sprite')
                idx += 1

        prof.start_profile('scaler.display_show')
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
        draw_y = (display_height - sprite_scaled_height) / 2

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
            int(draw_x),
            int(draw_y),
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
        v_scale = h_scale

        sprite_scaled_width = self.sprite.width * h_scale
        sprite_scaled_height = self.sprite.height * v_scale

        display_width = self.display.width
        display_height = self.display.height

        draw_x = (display_width / 2) - (sprite_scaled_width / 2)
        draw_y = (display_height - sprite_scaled_height) / 2

        self.common_bg()
        self.scaler.draw_sprite(
            self.sprite,
            int(draw_x),
            int(draw_y),
            self.image,
            h_scale=h_scale,
            v_scale=v_scale)

        self.show_prof()
        self.display.swap_buffers()

        time.sleep_ms(50)
        self.fps.tick()

    def do_refresh_clipping_square(self):
        """
        Do a demo of several diverse horizontal scale ratios
        """
        self.h_scales = [2]

        h_scale = self.h_scales[self.scale_id % len(self.h_scales)]
        v_scale = h_scale

        draw_x = 48 - (self.scaled_width / 2)

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
            int(self.draw_x),
            int(self.draw_y),
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


    def common_bg(self):
        self.display.fill(0x000000)
        width = self.screen_width
        height = self.screen_height

        if self.grid_lines:
            # Vertical lines
            for x in range(0, width, 8):
                self.display.line(x, 0, x, height, self.grid_lines_color)
            self.display.line(width-1, 0, width-1, height, self.grid_lines_color)

            # Horiz lines
            for y in range(0, height, 8):
                self.display.line(0, y, width, y, self.grid_lines_color)
            self.display.line(0, height-1, width, height-1, self.grid_lines_color)

        if self.grid_center:
            self.display.hline(0, height//2, width, self.grid_color)
            self.display.line(width//2, 0, width//2, height, self.grid_color)

    async def flip_dir(self):
        while True:
            if self.slide_sel == 'horiz':
                self.slide_sel = 'vert'
            else:
                self.slide_sel = 'horiz'
            await asyncio.sleep_ms(2000)

    def do_refresh(self):
        return self.current_loop()

    def create_lines(self):
        count = 64
        self.lines = []

        for i in range(count):
            y_start = 16 + int(i)
            y_start -= y_start % 2
            idx = math.floor(random.randrange(0,3))
            color = self.line_colors[idx]
            self.lines.append([int(0), int(y_start-16), int(95), int(y_start), color])

    def init_fps(self):
        self.fps_text = ColorWriter(
            self.display,
            font_vtks,
            36, 6,
            self.score_palette,
            fixed_width=4,
            color_format=fb.GS4_HMSB
        )
        self.fps_text.orig_x = 60
        self.fps_text.orig_y = 0
        self.fps_text.visible = True

        return self.fps_text

    async def start_fps_counter(self):
        await asyncio.sleep(5) # wait for things to stabilize first

        while True:
            fps = self.fps.fps()
            if fps is False:
                pass
            else:
                # num = self.mgr.pool.active_count
                # print(f"FPS: {fps_str} / {num} sprites")
                fps_str = "{: >6.2f}".format(fps)
                print(f"FPS: {fps_str}")

                # # ColorWriter.set_textpos(self.display.write_framebuf, 0, 0)
                # self.fps_text.row_clip = True
                # self.fps_text.render_text(fps_str)

            await asyncio.sleep(1)

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

    def load_sprite(self, load_type):
        sprite_type = load_type

        self.sprite = self.mgr.get_sprite_type(sprite_type)
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
            sprite_type=SPRITE_TEST_GRID_SPEED,
            sprite_class=TestGrid)

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
