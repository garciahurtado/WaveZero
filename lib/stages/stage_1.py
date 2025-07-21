from anim.palette_rotate_one import PaletteRotateOne
from colors.color_util import BGR565
from scaler.const import DEBUG
from sprites.sprite_registry import registry
from sprites.types.laser_wall import LaserWall
from sprites.types.test_skull import TestSkull
from sprites.types.warning_wall import WarningWall
from sprites.types.white_line import WhiteLine
from sprites.types.white_line_vert import WhiteLineVert
from stages.events import Event
from stages.stage import Stage
from sprites.sprite_types import *
from colors.palettes import convert_hex_palette, PALETTE_FIRE
import micropython

class Stage1(Stage):
    def __init__(self, sprite_manager):
        super().__init__(sprite_manager)

        self.base_speed = base_speed = -10
        # self.base_speed = wall_speed = base_speed = 0
        wall_speed = base_speed * 2
        fire_palette = None
        shared_palette = None

        spawn_z = 500
        line_height = 16

        # Times in ms
        big_wait = 5000
        med_wait = 4000
        small_wait = 2000
        tiny_wait = 500

        evt = self.events
        evt.sprite_manager = sprite_manager

        self.load_types()
        # self.init_palettes()

        # You can also add events programmatically:
        #
        # evt_list = []
        # for c in range(2):
        #     for r in range(2):
        #         evt_list.append(evt.spawn(SPRITE_TEST_SKULL, lane=c, y=r*line_height, z=spawn_z, speed=self.base_speed))

        self.sequence([
            # evt.multi(evt_list),
            evt.multi([
                # evt.spawn(SPRITE_BARRIER_LEFT_x2, lane=0, z=spawn_z, speed=wall_speed),
                # evt.spawn(SPRITE_BARRIER_LEFT_x2, lane=0, y=line_height, z=spawn_z, speed=wall_speed),

                # evt.spawn(SPRITE_BARRIER_LEFT, lane=3, z=spawn_z, speed=wall_speed),
                # evt.spawn(SPRITE_BARRIER_LEFT_x2, lane=3, y=line_height, z=spawn_z, speed=wall_speed),

                # evt.spawn(SPRITE_TEST_SKULL, lane=0, z=spawn_z, speed=wall_speed),
                # evt.spawn(SPRITE_TEST_SKULL, lane=0, y=line_height, z=spawn_z, speed=wall_speed),
                # evt.spawn(SPRITE_TEST_SKULL, lane=0, y=line_height*2, z=spawn_z, speed=wall_speed),
                # evt.spawn(SPRITE_TEST_SKULL, lane=0, y=line_height*3, z=spawn_z, speed=wall_speed),
                #
                evt.spawn(SPRITE_TEST_SKULL, lane=1, z=spawn_z, speed=wall_speed),
                evt.spawn(SPRITE_TEST_SKULL, lane=1, y=line_height, z=spawn_z, speed=wall_speed),
                evt.spawn(SPRITE_TEST_SKULL, lane=1, y=line_height * 2, z=spawn_z, speed=wall_speed),
                evt.spawn(SPRITE_TEST_SKULL, lane=1, y=line_height * 3, z=spawn_z, speed=wall_speed),
                #
                # evt.spawn(SPRITE_TEST_SKULL, lane=2, z=spawn_z, speed=wall_speed),
                # evt.spawn(SPRITE_TEST_SKULL, lane=2, y=line_height, z=spawn_z, speed=wall_speed),
                # evt.spawn(SPRITE_TEST_SKULL, lane=2, y=line_height * 2, z=spawn_z, speed=wall_speed),
                # evt.spawn(SPRITE_TEST_SKULL, lane=2, y=line_height * 3, z=spawn_z, speed=wall_speed),
                # evt.spawn(SPRITE_TEST_SKULL, lane=2, y=line_height * 4, z=spawn_z, speed=wall_speed),
                # evt.spawn(SPRITE_TEST_SKULL, lane=2, y=line_height * 5, z=spawn_z, speed=wall_speed),
                # evt.spawn(SPRITE_TEST_SKULL, lane=2, y=line_height * 6, z=spawn_z, speed=wall_speed),

                # evt.spawn(SPRITE_TEST_SKULL, lane=3, z=spawn_z, speed=wall_speed),
                # evt.spawn(SPRITE_TEST_SKULL, lane=3, y=line_height, z=spawn_z, speed=wall_speed),
                # evt.spawn(SPRITE_TEST_SKULL, lane=3, y=line_height * 2, z=spawn_z, speed=wall_speed),
                # evt.spawn(SPRITE_TEST_SKULL, lane=3, y=line_height * 3, z=spawn_z, speed=wall_speed),

                # evt.spawn(SPRITE_TEST_SKULL, lane=4, z=spawn_z, speed=wall_speed),
                # evt.spawn(SPRITE_TEST_SKULL, lane=4, y=line_height, z=spawn_z, speed=wall_speed),
                # evt.spawn(SPRITE_TEST_SKULL, lane=4, y=line_height * 2, z=spawn_z, speed=wall_speed),
                # evt.spawn(SPRITE_TEST_SKULL, lane=4, y=line_height * 3, z=spawn_z, speed=wall_speed),

                evt.wait(big_wait)],
                repeat=2),
            evt.wait(big_wait)],
            repeat=1)

            # evt.multi([
            #     evt.spawn(SPRITE_BARRIER_RIGHT_x2, lane=0, z=spawn_z),
            #     evt.spawn(SPRITE_BARRIER_LEFT_x2, lane=3, z=spawn_z),
            #     evt.wait(tiny_wait)],
            #     repeat=16),
            # evt.wait(small_wait),

        # self.wait(500)
        # asyncio.create_task(self.rotate_palette())

    def init_palettes(self):
        """ This is just so that the image and palette will be loaded ahead of the spawns"""

        sprite, _ = self.sprite_manager.spawn(SPRITE_WHITE_LINE)
        shared_pal = self.sprite_manager.sprite_palettes[SPRITE_WHITE_LINE]
        self.fire_palette = convert_hex_palette(PALETTE_FIRE, color_mode=BGR565)

        sprite, _ = self.sprite_manager.spawn(SPRITE_WHITE_LINE_VERT)
        self.sprite_manager.sprite_palettes[SPRITE_WHITE_LINE_VERT] = shared_pal
        self.shared_palette = shared_pal

        print(micropython.mem_info())

        self.color_anim = PaletteRotateOne(self.shared_palette, self.fire_palette, 100, 0)
        self.color_anim.stop()

        print(micropython.mem_info())

        return True

    def load_types(self):
        registry.add_type(
            SPRITE_TEST_SKULL,
            TestSkull,
            speed=self.base_speed)

        registry.add_type(
            SPRITE_BARRIER_LEFT,
            WarningWall,
            speed=self.base_speed)

        registry.add_type(
            SPRITE_BARRIER_LEFT_x2,
            WarningWall,
            speed=self.base_speed,
            repeats=3,
            repeat_spacing=16)


        registry.add_type(
            SPRITE_BARRIER_RIGHT,
            WarningWall,
            image_path="/img/road_barrier_yellow_inv_32.bmp",
            speed=self.base_speed)

        registry.add_type(
            SPRITE_BARRIER_RIGHT_x2,
            WarningWall,
            image_path="/img/road_barrier_yellow_inv_32.bmp",
            speed=self.base_speed,
            repeats=2,
            repeat_spacing=24)

        # registry.add_type(
        #     SPRITE_LASER_WALL,
        #     LaserWall,
        #     speed=self.base_speed)
        #
        # registry.add_type(
        #     SPRITE_LASER_WALL_x2,
        #     LaserWall,
        #     repeats=2,
        #     repeat_spacing=24)
        #
        # registry.add_type(
        #     SPRITE_LASER_WALL_x5,
        #     LaserWall,
        #     repeats=5,
        #     repeat_spacing=24)
        #
        # registry.add_type(
        #     SPRITE_WHITE_LINE,
        #     WhiteLine,
        #     image_path="/img/test_white_line.bmp",
        #     width=24,
        #     height=2,
        #     speed=self.base_speed)
        #
        # registry.add_type(
        #     SPRITE_WHITE_LINE_x2,
        #     WhiteLine,
        #     image_path="/img/test_white_line.bmp",
        #     width=24,
        #     height=2,
        #     repeats=2,
        #     speed=self.base_speed)
        #
        # registry.add_type(
        #     SPRITE_WHITE_LINE_x5,
        #     WhiteLine,
        #     image_path="/img/test_white_line.bmp",
        #     width=24,
        #     height=2,
        #     repeats=5,
        #     repeat_spacing=24,
        #     speed=self.base_speed)
        #
        # registry.add_type(
        #     SPRITE_WHITE_LINE_VERT,
        #     WhiteLineVert,
        #     image_path="/img/test_white_line_vert.bmp",
        #     width=2,
        #     height=24,
        #     speed=self.base_speed)
        #
        # registry.add_type(
        #     SPRITE_WHITE_LINE_VERT_x3,
        #     WhiteLineVert,
        #     image_path="/img/test_white_line_vert.bmp",
        #     width=2,
        #     height=24,
        #     repeats=3,
        #     speed=self.base_speed)
        #
        # registry.add_type(
        #     SPRITE_WHITE_LINE_VERT_x6,
        #     WhiteLineVert,
        #     image_path="/img/test_white_line_vert.bmp",
        #     width=2,
        #     height=24,
        #     repeats=6,
        #     repeat_spacing=24,
        #     speed=self.base_speed)

        # registry.add_type(
        #     SPRITE_ALIEN_FIGHTER,
        #     AlienFighter,
        #     image_path="/img/alien_fighter.bmp",
        #     width=24,
        #     height=16,
        #     speed=0)


