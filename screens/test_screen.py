import _thread

import utime
import uasyncio as asyncio

import gc

import math
import random

from input import game_input
from scaler.const import DEBUG
from screens.screen import PixelBounds

from scaler.sprite_scaler import SpriteScaler
from screens.test_screen_base import TestScreenBase
from sprites.renderer_scaler import RendererScaler
from sprites.sprite_manager_3d import SpriteManager3D
from sprites.sprite_registry import registry
from sprites.types.cherries_16 import Cherries16
from sprites.types.gameboy import GameboySprite
from sprites.types.test_pyramid import TestPyramid
from sprites.types.test_skull import TestSkull

from sprites.types.test_square import TestSquare
from sprites.types.test_heart import TestHeart
from sprites.types.test_grid import TestGrid
from sprites.types.warning_wall import WarningWall

gc.collect()

from sprites.sprite_manager_2d import SpriteManager2D
from sprites.sprite_types import SPRITE_TEST_SQUARE, SPRITE_TEST_HEART, SPRITE_TEST_GRID, SpriteType, \
    SPRITE_TEST_PYRAMID, SPRITE_GAMEBOY, SPRITE_CHERRIES, SPRITE_TEST_SKULL, SPRITE_BARRIER_LEFT
from profiler import Profiler as prof

from colors.color_util import hex_to_565
from colors.color_util import GREY
from colors.color_util import WHITE
from micropython import const

class TestScreen(TestScreenBase):
    debug = True
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
    sprite_type= None           # Numeric ID of sprite type (const)
    sprite:SpriteType = None    # SpriteType / meta (not instance)
    inst = None                 # Sprite instance

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
    phy = None # Physics Object

    STATE_START = const(1)
    STATE_DIR_LEFT = const(2)
    STATE_DIR_RIGHT = const(3)
    STATE_DIR_UP = const(4)
    STATE_DIR_DOWN = const(5)

    state_names = [
        'STATE_NONE',
        'STATE_START',
        'STATE_DIR_LEFT',
        'STATE_DIR_RIGHT',
        'STATE_DIR_UP',
        'STATE_DIR_DOWN',
    ]
    state = None
    last_state = None

    last_perf_dump_ms = None
    instances = []
    lines = []
    # line_color = colors.hex_to_rgb(0xFFFFFF)

    image = None
    num_cols = None
    num_rows = None
    sep = 2
    sep_dir = 1
    bg_color = hex_to_565(GREY)
    x_offset = 0
    y_offset = 0
    center_x = 0
    center_y = 0
    all_coords = [] # list of x/y tuples

    def __init__(self, display, *args, **kwargs):
        """ Thread #2 """
        # gc.collect()
        # _thread.start_new_thread(self.init_thread_2, [])

        super().__init__(display, margin_px=16)
        print()
        print(f"=== Testing performance of {self.num_sprites} sprites ===")
        print()

        self.idx = 0

        print(f"Free memory __init__: {gc.mem_free():,} bytes")

        # self.x_vals = [(0*i) for i in range(num_sprites)]
        # self.y_vals = [(0*i) for i in range(num_sprites)]
        # self.y_vals = [(random.randrange(-30, 30)) for _ in range(num_sprites)]

        self.sprite_scales = [random.choice(range(0, 9)) for _ in range(self.num_sprites)]

        # self.create_lines()

        self.renderer = RendererScaler(display)
        self.scaler = self.renderer.scaler
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
        self.center_x = self.screen_width // 2
        self.center_y = self.screen_height // 2

    def create_line_colors(self):
        self.line_colors = [hex_to_565(0xFF0000),
                       hex_to_565(0x00FF00),
                       hex_to_565(0x0000FF)]

        self.rainbow_colors = [
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

    def create_sprite_manager(self, num_sprites, renderer):
        print("-- Creating Sprite Manager...")

        self.scaler = renderer.scaler
        self.max_sprites = num_sprites
        self.mgr = SpriteManager2D(self.display, renderer, self.max_sprites)

        # self.mgr = SpriteManager3D(
        #     self.display,
        #     renderer,
        #     max_sprites=self.max_sprites,
        #     camera=self.camera,
        # )
        return self.mgr

    def run(self):
        self.running = True
        # self.load_types()
        self.init_common()

        loop = asyncio.get_event_loop()
        loop.create_task(self.start_display_loop())

        test = 'zoom_heart'
        method = None

        # self.create_line_colors()

        if test == 'zoom_heart':
            self.load_sprite(SPRITE_BARRIER_LEFT, WarningWall)
            self.init_beating_heart()
            method = self.do_refresh_zoom_in
        elif test == 'zoom_sq':
            self.load_sprite(SPRITE_TEST_SQUARE, TestSquare)
            self.init_beating_heart()
            method = self.do_refresh_zoom_in
        if test == 'scale_control':
            self.load_sprite(SPRITE_TEST_HEART, TestHeart)
            self.init_score()
            self.init_scale_control()
            method = self.do_refresh_scale_control
        elif test == 'grid1':
            self.color_demo = False
            self.load_sprite(SPRITE_TEST_HEART, TestHeart)
            self.init_grid()
            method = self.do_refresh_grid
        elif test == 'grid2':
            self.load_sprite(SPRITE_GAMEBOY, GameboySprite)
            self.init_grid()
            method = self.do_refresh_grid
        elif test == 'grid3':
            self.load_sprite(SPRITE_TEST_SKULL, TestSkull)
            self.init_grid()
            method = self.do_refresh_grid
        elif test == 'clipping':
            self.load_sprite(SPRITE_CHERRIES, Cherries16)
            self.init_clipping()
            method = self.do_refresh_clipping
        # else:
        #     print(f"TEST WAS {test}")
        #     raise Exception(f"Invalid method: {method}")

        self.refresh_method = getattr(self, method.__name__, None)

        if self.fps_enabled:
            self.fps_counter_task = asyncio.create_task(self.start_fps_counter())

        asyncio.run(self.start_update_loop())


    async def start_update_loop(self):
        print(f"-- ... MAIN LOOP STARTING ON THREAD #{_thread.get_ident()} ... --")

        """ All top level tasks / threads go here. Once all of these finish, the program ends"""
        await asyncio.gather(
            self.update_loop(),
        )

    async def update_loop(self):
        """ Counterpart to do_refresh and intended for world updates (speed, position, scale, lifetime mgmt...)"""
        start_time_ms = self.last_update_ms = utime.ticks_ms()
        self.last_perf_dump_ms = start_time_ms

        print(f" == STARTING UPDATE LOOP - ON THREAD #{_thread.get_ident()} ==")

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
                await asyncio.sleep(1 / 160)

        except asyncio.CancelledError:
            return False

    def get_elapsed(self):
        return utime.ticks_ms() - self.last_tick

    def init_common(self, num_sprites=1):
        self.max_sprites = num_sprites
        renderer = RendererScaler(self.display)
        self.mgr = self.create_sprite_manager(num_sprites, renderer)

        self.phy = self.mgr.phy
        if prof and prof.enabled:
            prof.fps = self.fps

    def init_grid(self):
        # self.sprite = self.mgr.get_meta(self.inst)

        sprite_width = self.sprite.width
        sprite_height = self.sprite.height

        one_scales1 = list(self.one_scales.keys())
        one_scales1_rev = one_scales1.copy()
        one_scales1_rev.reverse()

        one_scales2 = one_scales1.copy()
        one_scales2.reverse()

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
                all_coords.append([draw_x+8, draw_y+8])

        self.all_coords = all_coords

    async def start_display_loop(self):
        if DEBUG:
            print("== STARTING DISPLAY LOOP ON TEST_SCREEN.PY ==")

        while True:
            self.refresh_method()
            await asyncio.sleep_ms(1)

    def init_beating_heart(self):
        # self.sprite = self.mgr.get_meta(self.sprite)
        self.inst, idx = self.mgr.pool.get(self.sprite_type)

        h_scales1 = list(self.all_scales.keys())
        h_scales1.sort()

        """ Double up the scale """
        h_scales2 = h_scales1.copy()
        h_scales2.reverse()

        self.h_scales = h_scales1

    def init_scale_control(self):
        self.init_fps()
        self.inst, idx = self.mgr.pool.get(self.sprite_type, self.sprite)

        self.draw_x = self.display.width // 2
        self.draw_y = self.display.height // 2
        self.image = self.mgr.sprite_images[self.sprite_type][-1]

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

        self.input_handler = input_rotary.GameInput(half_step=True)
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

    def scale_control_left(self):
        if self.scale_id > 0:
            self.scale_id -= 1
            if self.debug:
                scale = self.h_scales[self.scale_id]
                self.sprite.scale = scale

    def init_clipping(self):
        self.inst, idx = self.mgr.pool.get(self.sprite_type, self.sprite)

        # self.sprite_type.set_flag(self.inst, FLAG_PHYSICS, True)
        self.phy.set_pos(self.inst, self.center_x, self.center_y)
        self.curr_dir = 'horiz'
        self.bounce_count = 0
        self.inst.speed = self.base_speed = 0.2
        self.h_scale = self.v_scale = 4

        self.bounds = self.scaler.framebuf.bounds
        self.scaled_width = math.ceil(self.sprite.width * self.h_scale)
        self.scaled_height = math.ceil(self.sprite.height * self.v_scale)
        self.set_state(self.STATE_START)

    def do_refresh_grid(self):
        """
        Show a grid of heart Sprites
        """
        prof.start_frame()

        self.idx = 0
        inst = self.inst
        row_sep = self.sprite.width
        col_sep = self.sprite.width

        self.display.fill(0x000000)

        for c in range(self.num_cols):
            for r in range(self.num_rows):

                self.phy.set_pos(inst,
                                 c * col_sep + 8,
                                 r * row_sep + 8)

                if self.grid_beat or self.fallout:
                    scale_factor = (self.scale_id + self.idx) % self.scale_source_len
                    self.scale_id = self.scale_id + 1
                    self.h_scale = self.scale_source[scale_factor]
                    self.v_scale = self.h_scale

                    self.scaled_width = self.sprite.height * self.h_scale
                    self.scaled_height = self.sprite.height * self.v_scale

                self.scaler.draw_sprite(
                    self.sprite,
                    inst,
                    self.image,
                    h_scale=self.h_scale,
                    v_scale=self.v_scale)

                self.idx = self.idx + 1

        if self.color_demo:
            new_color = self.rainbow_colors[self.color_idx % self.color_len]
            self.sprite_palette.set_hex(3, new_color)
            self.color_idx += 1


        self.display.show()

        self.show_prof()
        self.fps.tick()

    def do_refresh_zoom_in(self):
        """
        Do a zoom in demo of increasingly higher scale ratios
        """

        h_scale = self.h_scales[self.scale_id % len(self.h_scales)]
        v_scale = h_scale
        h_scale = v_scale = 1 # DEBUG!!

        sprite_scaled_width = self.sprite.width * h_scale
        sprite_scaled_height = self.sprite.height * v_scale

        display_width = self.display.width
        display_height = self.display.height

        draw_x = (display_width / 2) - (sprite_scaled_width / 2)
        draw_y = (display_height / 2) - (sprite_scaled_height / 2)

        if DEBUG:
            print("IN SCREEN about to draw_sprite:")
            print(f"  v_scale: {v_scale}")
            print(f"  h_scale: {h_scale}")
            print(f"  draw_x: {draw_x}")
            print(f"  draw_y: {draw_y}")
            print(f"  sprite_scaled_width: {sprite_scaled_width}")
            print(f"  sprite_scaled_height: {sprite_scaled_height}")

        self.display.fill(0x000000)
        self.scaler.draw_sprite(
            self.sprite,
            self.inst,
            self.image,
            # h_scale=h_scale,
            # v_scale=v_scale)
            h_scale=1,
            v_scale=1)

        self.scale_id += 1
        self.show_prof()
        self.display.show()

        self.fps.tick()

    def do_refresh_scale_control(self):
        """
        Do a zoom in demo of scales controlled by rotary input
        """

        h_scale = self.h_scales[self.scale_id]
        self.sprite.scale = v_scale = h_scale
        # self.sprite.scale = v_scale = h_scale = 6

        center_x = 48
        center_y = 32
        self.mgr.phy.set_pos(self.inst, center_x, center_y) # Center the sprite
        coords = self.mgr.phy.get_pos(self.inst)

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
        utime.sleep_ms(1)
        self.fps.tick()

    def do_refresh_clipping(self):
        """
        Do a demo of several diverse horizontal scale ratios
        """
        phy = self.phy
        scaled_width = self.scaled_width
        scaled_height = self.scaled_height

        x_max = 96
        x_min = 0 - scaled_width

        y_max = 64
        y_min = 0 - scaled_height

        state = self.state

        pos_x, pos_y = phy.get_pos(self.inst)
        draw_x, draw_y = phy.get_draw_pos(self.inst, scaled_width, scaled_height)
        inst = self.inst

        sprite_dims = PixelBounds(
            left = draw_x,
            right= draw_x + scaled_width,
            top = draw_y,
            bottom= draw_y + scaled_height
        )
        self.last_state = state

        """ Sprite center out of bounds """
        if not self.is_point_in_bounds([pos_x, pos_y]):
            """ Turn around when we reach the edges"""
            if state == self.STATE_DIR_LEFT:
                self.set_state(self.STATE_DIR_RIGHT)
                phy.set_pos(inst, self.bounds.left + 10, pos_y)
                phy.set_dir(inst, 1, 0)
            elif state == self.STATE_DIR_RIGHT:
                self.set_state(self.STATE_DIR_LEFT)
                phy.set_pos(inst, self.bounds.right - 1, pos_y)
                phy.set_dir(inst, -1, 0)
            elif state == self.STATE_DIR_UP:
                self.set_state(self.STATE_DIR_DOWN)
                phy.set_dir(inst, 0, 1)
            elif state == self.STATE_DIR_DOWN:
                self.set_state(self.STATE_DIR_UP)
                phy.set_dir(inst, 0, -1)

            return

        """ Sprite center within bounds """
        if state == self.STATE_START:
            self.set_state(self.STATE_DIR_LEFT)
            phy.set_dir(inst, -1, 0)
        elif state == self.STATE_DIR_LEFT and pos_x < self.half_width:
            print(f"LAST STATE: {self.state_names[self.last_state]}")

            if self.was_state(self.STATE_DIR_RIGHT):

                """ We crossed over the middle point, so change direction """
                self.set_state(self.STATE_DIR_UP)
                self.center_sprite(inst)
                phy.set_dir(inst, 0, -1)
        elif state == self.STATE_DIR_DOWN and pos_y < self.half_height:
            if self.was_state(self.STATE_DIR_UP):
                """ We crossed over the middle point, so restart """
                self.set_state(self.STATE_START)
                self.center_sprite(inst)
                phy.set_dir(inst, 0, 0)

        self.display.fill(0x000000)
        self.scaler.draw_sprite(
            self.sprite,
            self.inst,
            self.image,
            h_scale=self.h_scale,
            v_scale=self.v_scale)

        # self.scale_id += 1
        self.show_prof()
        self.display.show()
        self.fps.tick()

        if self.debug:
            names = self.state_names
            print(f" * LAST STATE:  {names[self.last_state]}")
            print(f" * STATE:       {names[self.state]}")
            print("--")

    def center_sprite(self, sprite):
        self.phy.set_pos(sprite, self.center_x, self.center_y)

    async def flip_dir(self):
        while True:
            if self.slide_sel == 'horiz':
                self.slide_sel = 'vert'
            else:
                self.slide_sel = 'horiz'
            await asyncio.sleep_ms(2000)

    def do_refresh(self):
        return self.refresh_method()

    def set_state(self, state):
        """ Manage the various valid states of this screen (State machine, not PIO)"""
        self.last_state = self.state
        self.state = state

    def was_state(self, state):
        if self.last_state == state:
            return True

        return False

    def create_lines(self):
        count = 64
        self.lines = []

        for i in range(count):
            y_start = 16 + int(i)
            y_start -= y_start % 2
            idx = math.floor(random.randrange(0,3))
            color = self.line_colors[idx]
            self.lines.append([int(0), int(y_start-16), int(95), int(y_start), color])


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
        self.last_tick = utime.ticks_ms()

    def load_types(self):
        raise DeprecationWarning

        registry.add_type(
            SPRITE_TEST_HEART,
            TestHeart)

        registry.add_type(
            SPRITE_TEST_SQUARE,
            TestSquare)

        registry.add_type(
            SPRITE_TEST_GRID,
            TestGrid)

        registry.add_type(
            SPRITE_TEST_PYRAMID,
            TestPyramid)

        registry.add_type(
            SPRITE_GAMEBOY,
            GameboySprite)

        registry.add_type(
            SPRITE_CHERRIES,
            Cherries16)

        registry.add_type(
            SPRITE_TEST_SKULL,
            TestSkull)

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
