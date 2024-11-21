import sys

from screen import Screen
from scaler.dma_scaler import DMAScaler

from sprites2.test_square import TestSquare
from sprites2.sprite_manager_2d import SpriteManager2D

from sprites2.sprite_types import SPRITE_TEST_SQUARE
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

    num_sprites = 1
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

    def __init__(self, display, *args, **kwargs):
        num_sprites = self.num_sprites

        super().__init__(display)
        print()
        print(f"=== Testing performance of {num_sprites} sprites ===")
        print()

        self.preload_images()
        self.fps_counter_task = asyncio.create_task(self.start_fps_counter())

        print(f"Free memory __init__: {gc.mem_free():,} bytes")

        # self.score_palette.set_rgb(0, colors.hex_to_rgb(BLACK))
        # self.score_palette.set_rgb(0, colors.hex_to_rgb(CYAN))

        self.base_x = 36
        self.base_y = 18

        self.x_vals = [(0*i) for i in range(num_sprites)]
        self.y_vals = [(0*i) for i in range(num_sprites)]
        # self.y_vals = [(random.randrange(-30, 30)) for _ in range(num_sprites)]

        self.sprite_scales = [random.choice(range(0, 9)) for _ in range(num_sprites)]

        self.init_camera()
        # self.init_fps()

        # display.fill(0x0000)
        display.fill(0xAA00)
        display.show()

        self.create_sprite_manager(display, num_sprites=num_sprites)

        """ Channels 0 and 1 are already reserved by the display driver """
        ch_2 = DMA()
        ch_3 = DMA()
        ch_4 = DMA()
        ch_5 = DMA()
        ch_6 = DMA()
        ch_7 = DMA()
        ch_8 = DMA()
        ch_9 = DMA()

        num_colors = 16

        self.scaler = DMAScaler(self.display, num_colors, ch_2, ch_3, ch_4, ch_5, ch_6, ch_7, ch_8, ch_9)

    def create_sprite_manager(self, display, num_sprites=0):
        self.check_mem()
        print("-- Creating Sprite Manager...")
        self.max_sprites = num_sprites
        self.mgr = SpriteManager2D(display, self.max_sprites, self.camera)
        self.load_types()

    def run(self):
        self.check_mem()
        self.create_sprites()

        loop = asyncio.get_event_loop()
        loop.create_task(self.start_display_loop())
        asyncio.run(self.start_main_loop())
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

        # self.create_lines()

        await asyncio.gather(
            asyncio.create_task(self.start_fps_counter()),
        )

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

    def do_refresh(self):
        """ Overrides parent method """
        self.display.fill(0xAA00)

        self.draw_image_group(self.one_sprite_image, self.one_sprite_meta, self.num_sprites, self.x_vals, self.y_vals)
        # self.display.show()
        self.scaler.reset()

        self.show_prof()
        self.fps.tick()

    def draw_image_group(self, image, meta, num=10, x_vals=[], y_vals=[]):
        img_width = meta.width
        img_height = meta.height

        num_sprites = num

        base_x = self.base_x
        base_y = self.base_y

        prof.start_profile('scaler.show_all')
        for i in range(num_sprites):
            # draw_x = abs(i*2 + base_x + x_vals[i])
            # draw_y = abs(i*2 + base_y + y_vals[i])

            #DEBUG#
            draw_x = 24
            draw_y = 12 + (15*i)

            draw_x = max(0, draw_x)
            draw_y = max(0, draw_y)

            draw_x = min(self.display.width, draw_x)
            draw_y = min(self.display.height, draw_y)

            # DEBUG
            # draw_x = 0
            # draw_y = 8 + (i*2)

            scale = self.sprite_scales[i]

            prof.start_profile('scaler.show_one')
            self.scaler.show(image, draw_x, draw_y, img_width, img_height, scale)
            prof.end_profile('scaler.show_one')

            # print(f" . COORDS: x:{draw_x} y:{draw_y} ")

        prof.end_profile('scaler.show_all')

    async def start_fps_counter(self):
        while True:
            fps = self.fps.fps()
            if fps is False:
                pass
            else:
                fps = int(fps)
                fps_str = "{: >6}".format(fps)
                print(f"FPS: {fps_str}")

                # # ColorWriter.set_textpos(self.display.write_framebuf, 0, 0)
                # self.fps_text.row_clip = True
                # self.fps_text.render_text(fps_str)


            await asyncio.sleep(1)

    def sprite_fps_test_wrapper(self):

        while True:
            self.sprite_fps_test_func()
            utime.sleep_ms(1)

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

    def create_sprites(self):
        num_sprites = self.num_sprites
        print(f"Creating {num_sprites} sprites")

        sprite_type = SPRITE_TEST_SQUARE
        meta = self.mgr.sprite_metadata[sprite_type]

        for i in range(0, num_sprites):
            sprite, _ = self.mgr.create(sprite_type)
            self.sprites.append(sprite)

        """ Create single sprite for simple tests """
        self.one_sprite = self.sprites[0]
        self.one_sprite_meta = meta
        self.one_sprite_image = self.mgr.sprite_images[sprite_type][-1]

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

    # async def refresh_display(self):
    #     # _thread.start_new_thread(self.sprite_fps_test_wrapper, [])
    #
    #     bg_color = colors.hex_to_565(CYAN)
    #     while True:
    #         self.display.fill(bg_color)
    #         # self.show_lines()
    #         # self.mgr.show()
    #         # self.fps_text.show(self.display)
    #         self.do_refresh()
    #
    #         await asyncio.sleep(1/100)

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
