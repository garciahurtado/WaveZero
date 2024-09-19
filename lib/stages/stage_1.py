import asyncio

from anim.palette_rotate_one import PaletteRotateOne
from color.color_util import BGR565, RGB565
from dump_object import dump_object
from sprites2.alien_fighter import AlienFighter
from sprites2.laser_wall import LaserWall
from sprites2.warning_wall import WarningWall
from stages.events import Event
from stages.stage import Stage
from sprites2.sprite_types import *
from sprites2.white_line import WhiteLine
from color.framebuffer_palette import FramebufferPalette as BufPalette
from color.palettes import PALETTE_UI_FLASH_TEXT, convert_hex_palette, PALETTE_SHIFT, PALETTE_FIRE
from color import color_util as colors
import micropython

class Stage1(Stage):
    base_speed = -50
    fire_palette = None
    shared_palette = None
    
    def __init__(self, sprite_manager):
        super().__init__(sprite_manager)

        spawn_z = 1500
        med_wait = 10000
        small_wait = 1000
        tiny_wait = 500

        Event.sprite_manager = sprite_manager
        evt = self.events

        self.load_types()
        # self.init_palettes()

        line_height = 24

        self.sequence([
            evt.multi([
                # evt.spawn(SPRITE_BARRIER_RIGHT_x2, lane=0, z=spawn_z),
                # evt.spawn(SPRITE_BARRIER_LEFT_x2, lane=3, z=spawn_z),
                evt.spawn(SPRITE_WHITE_LINE_VERT, lane=0, z=spawn_z),
                evt.spawn(SPRITE_WHITE_LINE_VERT, lane=5, z=spawn_z),
                evt.spawn(SPRITE_WHITE_LINE_x5, lane=0, z=spawn_z),
                # evt.spawn(SPRITE_WHITE_LINE_VERT_x3, lane=3, z=spawn_z),

                evt.wait(tiny_wait)],
                repeat=20),
            evt.wait(med_wait),

            # evt.multi([
            #     evt.spawn(SPRITE_BARRIER_RIGHT_x2, lane=0, z=spawn_z),
            #     evt.spawn(SPRITE_BARRIER_LEFT_x2, lane=3, z=spawn_z),
            #     evt.wait(tiny_wait)],
            #     repeat=16),
            # evt.wait(small_wait),

        ], repeat=1)
        # self.wait(500)

        # asyncio.create_task(self.rotate_palette())

    def init_palettes(self):
        """ This is just so that the image and palette will be loaded ahead of the spawns"""

        sprite, _ = self.sprite_manager.create(SPRITE_WHITE_LINE)
        shared_pal = self.sprite_manager.sprite_palettes[SPRITE_WHITE_LINE]
        self.fire_palette = convert_hex_palette(PALETTE_FIRE, color_mode=BGR565)

        sprite, _ = self.sprite_manager.create(SPRITE_WHITE_LINE_VERT)
        self.sprite_manager.sprite_palettes[SPRITE_WHITE_LINE_VERT] = shared_pal
        self.shared_palette = shared_pal

        print(micropython.mem_info())

        self.color_anim = PaletteRotateOne(self.shared_palette, self.fire_palette, 100, 0)
        self.color_anim.stop()

        print(micropython.mem_info())

        return True

    def load_types(self):
        mgr = self.sprite_manager
        mgr.add_type(
            sprite_type=SPRITE_BARRIER_LEFT,
            sprite_class=WarningWall,
            speed=self.base_speed)

        mgr.add_type(
            sprite_type=SPRITE_BARRIER_LEFT_x2,
            sprite_class=WarningWall,
            speed=self.base_speed,
            repeats=2,
            repeat_spacing=24)

        mgr.add_type(
            sprite_type=SPRITE_BARRIER_RIGHT,
            sprite_class=WarningWall,
            image_path="/img/road_barrier_yellow_inv.bmp",
            speed=self.base_speed)

        mgr.add_type(
            sprite_type=SPRITE_BARRIER_RIGHT_x2,
            image_path="/img/road_barrier_yellow_inv.bmp",
            sprite_class=WarningWall,
            speed=self.base_speed,
            repeats=2,
            repeat_spacing=24)

        # mgr.add_type(
        #     sprite_type=SPRITE_LASER_WALL,
        #     sprite_class=LaserWall,
        #     speed=self.base_speed)
        #
        # mgr.add_type(
        #     sprite_type=SPRITE_LASER_WALL_x2,
        #     sprite_class=LaserWall,
        #     repeats=2,
        #     repeat_spacing=24)
        #
        # mgr.add_type(
        #     sprite_type=SPRITE_LASER_WALL_x5,
        #     sprite_class=LaserWall,
        #     repeats=5,
        #     repeat_spacing=24)

        mgr.add_type(
            sprite_type=SPRITE_WHITE_LINE,
            sprite_class=WhiteLine,
            image_path="/img/test_white_line.bmp",
            width=24,
            height=2,
            speed=self.base_speed)

        mgr.add_type(
            sprite_type=SPRITE_WHITE_LINE_x2,
            sprite_class=WhiteLine,
            image_path="/img/test_white_line.bmp",
            width=24,
            height=2,
            repeats=2,
            speed=self.base_speed)

        mgr.add_type(
            sprite_type=SPRITE_WHITE_LINE_x5,
            sprite_class=WhiteLine,
            image_path="/img/test_white_line.bmp",
            width=24,
            height=2,
            repeats=5,
            repeat_spacing=24,
            speed=self.base_speed)

        mgr.add_type(
            sprite_type=SPRITE_WHITE_LINE_VERT,
            sprite_class=WhiteLine,
            image_path="/img/test_white_line_vert.bmp",
            width=2,
            height=24,
            speed=self.base_speed)

        mgr.add_type(
            sprite_type=SPRITE_WHITE_LINE_VERT_x3,
            sprite_class=WhiteLine,
            image_path="/img/test_white_line_vert.bmp",
            width=2,
            height=24,
            repeats=3,
            speed=self.base_speed)

        mgr.add_type(
            sprite_type=SPRITE_WHITE_LINE_VERT_x6,
            sprite_class=WhiteLine,
            image_path="/img/test_white_line_vert.bmp",
            width=2,
            height=24,
            repeats=6,
            repeat_spacing=24,
            speed=self.base_speed)

        mgr.add_type(
            sprite_type=SPRITE_ALIEN_FIGHTER,
            sprite_class=AlienFighter,
            image_path="/img/alien_fighter.bmp",
            width=24,
            height=16,
            speed=0)


