import random

import sys

from colors import color_util as colors
from mpdb.mpdb import Mpdb
from scaler.const import DEBUG
from scaler.sprite_scaler import SpriteScaler
from perspective_camera import PerspectiveCamera
from sprites2.sprite_manager_2d import SpriteManager2D
from sprites2.sprite_physics import CircleAnimation
from sprites2.test_flat import TestFlat
from sprites2.test_heart import TestHeart
from sprites2.test_skull import TestSkull
from sprites2.test_square import TestSquare
from ui_elements import ui_screen

from images.image_loader import ImageLoader
from road_grid import RoadGrid

from screens.screen import Screen
import uasyncio as asyncio
import utime

from sprites2.sprite_manager import SpriteManager
from sprites2.sprite_types import *

from micropython import const

class GameScreenTest(Screen):
    ground_speed: 0
    max_ground_speed: int = const(-700)
    max_sprites: int = 32

    grid: RoadGrid = None
    sun: Sprite = None
    sun_start_x = None
    camera: PerspectiveCamera
    enemies: SpriteManager = None
    saved_ground_speed = 0
    lane_width: int = const(24)
    num_lives: int = 4
    total_frames = 0
    last_update_ms = 0
    fps_every_n_frames = 30
    player = None
    last_perf_dump_ms = 0
    paused = False
    ui = None
    frames_elapsed = 0
    fps_enabled = True
    is_first = True # so that we only use the scaler on frame 2+
    inst_group = []

    def __init__(self, display, *args, **kwargs):
        super().__init__(display, *args, **kwargs)
        self.ground_speed = self.max_ground_speed
        display.fill(0x0000)
        self.init_camera()

        self.scaler = SpriteScaler(display)

        """ Config Live debugger """
        # mp_dbg = Mpdb(pause_dma_pio=True)
        # mp_dbg.add_break('/lib/scaler/sprite_scaler.py:230', _self=self.scaler, pause=True)
        # mp_dbg.set_trace()

        self.mgr = SpriteManager2D(self.display, self.max_sprites) # max sprites
        self.load_types()
        # self.load_sprite(SPRITE_TEST_FLAT)
        self.load_sprite(SPRITE_TEST_SKULL)
        # self.load_sprite(SPRITE_TEST_HEART)
        # self.load_sprite(SPRITE_TEST_SQUARE)
        self.preload_images()
        self.phy = self.mgr.phy

        patterns = self.scaler.dma.patterns.horiz_patterns
        pattern_keys = list(patterns.keys())
        pattern_keys.sort()
        short_keys = pattern_keys[0:16]
        self.scale_list = short_keys
        self.scale_list.reverse()

        print("__ SCALES: __")
        print(self.scale_list)

        str_out = ''
        for scale in pattern_keys:
            pattern = patterns[scale]

        self.init_sprites(display)

        self.display.fps = self.fps

    def preload_images(self):
        images = [
            {"name": "life.bmp", "width": 12, "height": 8},
        ]

        ImageLoader.load_images(images, self.display)

    def run(self):
        loop = asyncio.get_event_loop()
        loop.create_task(self.start_display_loop())

        self.display.fill(0x0)

        if self.fps_enabled:
            self.fps_counter_task = asyncio.create_task(self.start_fps_counter())

        print("-- Starting update_loop...")
        asyncio.run(self.start_main_loop())


    async def update_loop(self):
        start_time_ms = self.last_update_ms = utime.ticks_ms()
        self.last_perf_dump_ms = start_time_ms

        print(f"--- (game screen) Update loop Start time: {start_time_ms}ms ---")

        # update loop - will run until task cancellation
        try:
            while True:
                self.total_frames += 1
                now = utime.ticks_ms()
                elapsed = utime.ticks_diff(now, self.last_update_ms)
                elapsed = elapsed / 1000 # @TODO change to MS?
                total_elapsed = utime.ticks_diff(now, start_time_ms)
                self.last_update_ms = now

                if not self.paused:
                    self.grid.update_horiz_lines(elapsed)

                    # Update sprites circular motion
                    for sprite in self.inst_group:
                        self.phy.update_circ_pos(sprite, total_elapsed)

                await asyncio.sleep_ms(1)

        except asyncio.CancelledError:
            return False

    def do_refresh(self):
        """ Overrides parent method """
        if DEBUG:
            print(f"--------------------------")
            print(f"- START OF FRAME n. {self.frames_elapsed} - ")
            print(f"--------------------------")

            self.check_mem()

        self.display.fill(0x0)

        self.grid.show()
        self.ui.update_score(random.randint(0, 99999999))
        self.ui.show()

        # self.draw_corners()
        # self.draw_sprite_circle()

        inst = self.inst_group[0]
        h_scale = 0.750
        v_scale = 0.750
        self.scaler.draw_sprite(self.sprite, inst, self.image, h_scale=h_scale, v_scale=v_scale)

        self.display.show()
        self.fps.tick()

        if DEBUG:
            print(f"__________________________")
            print(f"- END OF FRAME n. {self.frames_elapsed} - ")
            print(f"__________________________")

        self.frames_elapsed += 1

    def draw_sprite_circle(self):
        scale_idx = 0
        for inst in self.inst_group:
            curr_scale = self.scale_list[scale_idx]
            self.scaler.draw_sprite(
                self.sprite, inst, self.image,
                h_scale=curr_scale, v_scale=curr_scale)
            scale_idx += 1

    def draw_corners(self):
        green = colors.hex_to_565(0x00FF00)
        red = colors.hex_to_565(0x0000FF)
        blue = colors.hex_to_565(0xFF0000)
        yellow = colors.hex_to_565(0x00FFFF)
        width = self.display.width-1
        height = self.display.height-1
        length = 16

        self.display.hline(0, 0,                    length, green)
        self.display.hline(width-length, 0,         length, green)
        self.display.hline(0, height,               length, green)
        self.display.hline(width-length, height,    length, green)

        self.display.line(0, 0, 0, length, green)
        self.display.line(width, 0, width, length, green)
        self.display.line(0, height, 0, height-length, green)
        self.display.line(width, height, width, height-length, green)

        self.display.hline(0, 0, 8, red)
        self.display.hline(0, 0, 4, blue)

    async def start_bus_profiler(self):
        while True:
            bus_prof = self.bus_prof
            if bus_prof is False: 
                pass
            else:
                self.bus_prof.display_profile_stats()

            await asyncio.sleep(1)
    def load_types(self):
        self.mgr.add_type(
            sprite_type=SPRITE_TEST_SKULL,
            sprite_class=TestSkull)

        self.mgr.add_type(
            sprite_type=SPRITE_TEST_HEART,
            sprite_class=TestHeart)

        self.mgr.add_type(
            sprite_type=SPRITE_TEST_FLAT,
            sprite_class=TestFlat)

    def load_sprite(self, sprite_type):
        """ Creates images if not exist, returns meta"""
        self.sprite_type = sprite_type
        self.sprite_meta = self.sprite = self.mgr.sprite_metadata[sprite_type]
        self.sprite_palette = self.mgr.get_palette(sprite_type)
        self.image = self.mgr.sprite_images[self.sprite_type][-1]
        return self.sprite_meta

    def init_camera(self):
        # Camera
        horiz_y: int = 16
        pos_y = 50
        max_sprite_height = -6

        self.camera = PerspectiveCamera(
            self.display,
            pos_x=0,
            pos_y=pos_y,
            pos_z=-int(pos_y/2),
            vp_x=0,
            vp_y=horiz_y,
            min_y=horiz_y+4,
            max_y=self.display.height + max_sprite_height,
            fov=90.0)

    def init_sprites(self, display):
        running_ms = 0

        # we should turn this 16 into a var
        for i in range(16):
            """ We give each sprite a slightly different 'birthday', so that the animation will place them in different
            parts of the circle """
            new_inst, idx = self.mgr.pool.get(self.sprite_type, self.sprite)
            new_inst.born_ms += running_ms
            self.phy.set_pos(new_inst, 50, 24)
            self.inst_group.append(new_inst)
            running_ms += 200

        self.ui = ui_screen(display, self.num_lives)
        self.grid = RoadGrid(self.camera, display, lane_width=self.lane_width)


