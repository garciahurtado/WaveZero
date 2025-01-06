import _thread
import sys

import time

from scaler.dma_interp_scaler import SpriteScaler
from scaler.scaling_patterns import ScalingPatterns
from scaler.sprite_scaler_test import init_test_sprite_scaling
from screens.screen import Screen
from scaler.dma_scaler import DMAScaler

from sprites2.test_square import TestSquare
from sprites2.test_heart import TestHeart
from sprites2.sprite_manager_2d import SpriteManager2D

from sprites2.sprite_types import SPRITE_TEST_SQUARE, SPRITE_TEST_HEART
import math
from profiler import Profiler as prof

from images.image_loader import ImageLoader

import fonts.vtks_blocketo_6px as font_vtks
from rp2 import DMA

from font_writer_new import ColorWriter

import utime
import uasyncio as asyncio
import gc

from perspective_camera import PerspectiveCamera
from color import color_util as colors
from color.framebuffer_palette import FramebufferPalette
import framebuf as fb
import random


CYAN =  0x00FFFF
GREEN = 0x00FF00
BLACK = 0x000000

class TestScreen(Screen):
    screen_width = 96
    screen_height = 64
    scale_id = 0

    base_x = 0
    base_y = 0
    delta_y = 2
    delta_x = 2
    draw_y_dir = 1
    draw_x_dir = -1
    draw_y = 0
    draw_x = 0
    slide_sel = 'vert'

    num_sprites = 1
    scaler_num_sprites = 1
    sprite_max_z = 1000
    display_task = None

    last_perf_dump_ms = None
    fps_text: ColorWriter
    sprites = []
    lines = []
    # line_color = colors.hex_to_rgb(0xFFFFFF)
    line_colors = [ colors.hex_to_565(0xFF0000),
                    colors.hex_to_565(0x00FF00),
                    colors.hex_to_565(0x0000FF)]
    score_palette = FramebufferPalette(16, color_mode=fb.GS4_HMSB)
    mgr = None
    scaler = None

    fps_counter_task = None
    sprite = None
    sep = 2
    sep_dir = 1
    bg_color = colors.hex_to_565(CYAN)

    def __init__(self, display, *args, **kwargs):
        super().__init__(display)
        print()
        print(f"=== Testing performance of {self.num_sprites} sprites ===")
        print()
        patt = ScalingPatterns()

        self.sprite_type = SPRITE_TEST_SQUARE
        self.preload_images()
        self.fps_counter_task = asyncio.create_task(self.start_fps_counter())

        print(f"Free memory __init__: {gc.mem_free():,} bytes")

        # self.x_vals = [(0*i) for i in range(num_sprites)]
        # self.y_vals = [(0*i) for i in range(num_sprites)]
        # self.y_vals = [(random.randrange(-30, 30)) for _ in range(num_sprites)]

        self.sprite_scales = [random.choice(range(0, 9)) for _ in range(self.num_sprites)]

        self.init_camera()
        self.init_fps()
        self.create_lines()

        self.create_sprite_manager(display, num_sprites=10)
        self.scaler = SpriteScaler(self.display)
        self.scaler.prof = prof

        self.h_scales = [0.5, 0.75, 1.0, 1.5, 2.0, 3.0]
        self.v_scales = [0.5, 1.0, 1.0, 1.6, 2.0, 3.0]
        self.all_scales = patt.get_horiz_patterns()

    def create_sprite_manager(self, display, num_sprites=0):
        self.check_mem()
        print("-- Creating Sprite Manager...")
        self.max_sprites = num_sprites
        self.mgr = SpriteManager2D(display, self.max_sprites, self.camera)
        self.load_types()

    def run(self):
        self.running = True

        self.check_mem()
        # self.sprite_type = SPRITE_TEST_HEART
        # self.load_sprite(SPRITE_TEST_HEART)

        self.sprite_type = SPRITE_TEST_SQUARE
        self.load_sprite(SPRITE_TEST_SQUARE)

        # loop = asyncio.get_event_loop()
        # loop.create_task(self.start_display_loop())
        asyncio.run(self.start_display_loop())
        self.check_mem()

    def preload_images(self):
        images = [
            # {"name": "bike_sprite.bmp", "width": 32, "height": 22, "color_depth": 4},
            # {"name": "laser_wall.bmp", "width": 24, "height": 10, "color_depth": 4},
            # {"name": "laser_orb_grey.bmp", "width": 16, "height": 16, "color_depth": 4},
        ]

        ImageLoader.load_images(images, self.display)

    async def start_main_loop(self):
        print("-- Starting main Loop ...")
        self.check_mem()

        await asyncio.gather(
            asyncio.create_task(self.start_fps_counter()),
            self.do_update(),
        )

    def do_update(self):
        print(f" = EXEC ON CORE {_thread.get_ident()} (do_update)")

    def do_refresh_clipping_square(self):
        """
        Do a heart beating demo of several diverse horizontal scale ratios
        """
        sprite = self.mgr.get_meta(self.sprite)
        image = self.mgr.sprite_images[self.sprite_type][-1]

        self.h_scales = [2]

        h_scale = self.h_scales[self.scale_id % len(self.h_scales)]
        v_scale = h_scale

        sprite_scaled_width = math.ceil(sprite.width * h_scale)
        sprite_scaled_height = math.ceil(sprite.height * v_scale)
        # draw_x = 48 - (sprite_scaled_width / 2)

        x_max = 96
        x_min = 0 - sprite_scaled_width

        y_max = 64
        y_min = 0 - sprite_scaled_height

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


        self.display.fill(0xFFFFFF)
        self.scaler.draw_sprite(
            sprite,
            int(self.draw_x),
            int(self.draw_y),
            image,
            h_scale=h_scale,
            v_scale=v_scale)

        self.scale_id += 1
        self.show_prof()
        self.display.swap_buffers()
        time.sleep_ms(10)
        self.fps.tick()


    def do_refresh_beating_heart(self):
        """
        Do a heart beating demo of several diverse horizontal scale ratios
        """
        sprite = self.mgr.get_meta(self.sprite)
        image = self.mgr.sprite_images[self.sprite_type][-1]

        # h_scales1 = [0.125, 0.250, 0.375, 0.500, 0.625, 0.750, 0.875, 1.0, 1.500, 2.0, 2.500, 3, 3.500, 4, 4.500, 5]
        h_scales1 = list(self.all_scales.keys())
        h_scales1.sort()
        h_scales2 = h_scales1.copy()
        h_scales2.reverse()

        self.h_scales = h_scales1 + h_scales2

        h_scale = self.h_scales[self.scale_id % len(self.h_scales)]
        v_scale = h_scale

        sprite_scaled_width = math.ceil(sprite.width * h_scale)
        sprite_scaled_height = math.ceil(sprite.height * v_scale)
        draw_x = 48 - (sprite_scaled_width / 2)
        draw_y = 32 - ((sprite_scaled_height) / 2)

        self.display.fill(0xFFFFFF)
        self.scaler.draw_sprite(
            sprite,
            int(draw_x),
            int(draw_y),
            image,
            h_scale=h_scale,
            v_scale=v_scale)

        self.scale_id += 1
        self.show_prof()
        self.display.swap_buffers()
        time.sleep_ms(10)
        self.fps.tick()

    def do_refresh(self):
        return self.do_refresh_clipping_square()
        # return self.do_refresh_beating_heart()

        """ Overrides parent method """
        # print(f" = EXEC ON CORE {_thread.get_ident()} (do_refresh)")

        meta = self.mgr.get_meta(self.sprite)
        image = self.mgr.sprite_images[self.sprite_type][-1]

        # self.create_lines()
        # self.show_lines()

        """ Working vertical scaling ratios:
            works: 2/3, 1/2, 1/3, 1/4, 1/5, 1/6, 1/8, 1/10, 1/12, 1/16
            dubious: 1/7 , 0.75 (use 0.76)
            upscales = [1, 2, 4, 8] # only power of 2 upscales working, why??
        """

        # print(f"\n=== Testing X:{scale_x * 100}% // Y:{scale_y * 100}% scaling ===")
        self.h_scales = [3, 2, 1.5, 1, 0.5, 1, 0.5, 1, 1.5, 2, 3]
        self.v_scales = [3, 2, 1.5, 1, 1, 1, 1, 1, 1.5, 2, 3]

        h_scale = self.h_scales[self.scale_id]
        v_scale = self.v_scales[self.scale_id]
        h_scale = 2
        v_scale = 2

        draw_y = draw_x = 0

        prof.start_profile('scaler.screen_prep')
        sprite_width = meta.width
        sprite_height = meta.height
        sprite_scaled_width = math.ceil(sprite_width * h_scale)
        sprite_scaled_height = math.ceil(sprite_height * v_scale)

        max_cols = 12
        max_rows = 10

        num_cols = min(self.screen_width//sprite_scaled_width, max_cols)
        num_rows = min(self.screen_height//sprite_scaled_height, max_rows)
        # num_cols = num_rows = 1

        num_sprites = 0
        sep_max = 20

        self.sep = 0
        self.display.fill(0xFFFFFF)
        prof.end_profile('scaler.screen_prep')

        # print(f"\tSCALER Drawing {width_step}x{height_step} = {width_step*height_step} sprites")
        for c in range(num_cols):
            for r in range(num_rows):
                prof.start_profile('scaler.draw_sprite')
                self.scaler.draw_sprite(
                    meta,
                    draw_x+(c*sprite_scaled_width)+(self.sep*c),
                    draw_y+(r*sprite_scaled_height),
                    image,
                    h_scale=h_scale,
                    v_scale=v_scale)
                prof.end_profile('scaler.draw_sprite')
                num_sprites += 1

        # self.sep += 2 * self.sep_dir

        if (self.sep > sep_max) or (self.sep < 2):
            self.sep_dir *= -1


        # self.scale_id += 1
        # if self.scale_id >= len(self.h_scales):
        #     self.scale_id = 0

        self.show_prof()
        self.display.swap_buffers()
        self.fps.tick()

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
        while True:
            fps = self.fps.fps()
            if fps is False:
                pass
            else:
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

        for i, sprite in enumerate(self.sprites):
            sprite.z = sprite.z + 6
            sprite.update(elapsed)
            # print(f"z: {sprite.z}")
        self.last_tick = utime.ticks_ms()

    # async def display_line_test(self):
    #     while True:
    #         self.mgr.update(0)
    #         await asyncio.sleep(1 / 60)

    def load_sprite(self, load_type):
        num_sprites = self.num_sprites
        print(f"Creating {num_sprites} sprites")

        sprite_type = load_type
        meta = self.mgr.sprite_metadata[sprite_type]

        """ Due to a current limitation / feature, the mgr.sprite_images array is not populated until at least one sprite of that
        type is created. """
        for i in range(0, num_sprites):
            sprite, _ = self.mgr.create(sprite_type)
            self.sprites.append(sprite)

        self.sprite = self.sprites[0]
        self.sprite_img = self.mgr.sprite_images[sprite_type]

        """ Create single sprite for simple tests """

    def load_types(self):
        # self.mgr.add_type(
        #     sprite_type=SPRITE_LASER_ORB,
        #     sprite_class=LaserOrb,
        #     width=16,
        #     height=16,
        #     speed=0)

        self.mgr.add_type(
            sprite_type=SPRITE_TEST_SQUARE,
            sprite_class=TestSquare,
            speed=0)

        self.mgr.add_type(
            sprite_type=SPRITE_TEST_HEART,
            sprite_class=TestHeart,
            speed=0)

        # self.mgr.add_type(
        #     sprite_type=SPRITE_LASER_WALL,
        #     sprite_class=SpriteType,
        #     image_path="/img/laser_wall.bmp",
        #     width=24,
        #     height=10,
        #     speed=0)

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
