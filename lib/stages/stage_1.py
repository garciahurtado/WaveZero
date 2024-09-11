import asyncio

from dump_object import dump_object
from sprites2.laser_wall import LaserWall
from sprites2.warning_wall import WarningWall
from stages.events import Event
from stages.stage import Stage
from sprites2.sprite_types import *
from sprites2.white_line_x5 import WhiteLineX5

class Stage1(Stage):
    base_speed = -80

    def __init__(self, sprite_manager):
        super().__init__(sprite_manager)

        spawn_z = 1000
        small_wait = 5000
        tiny_wait = 200

        Event.sprite_manager = sprite_manager
        evt = self.events

        self.load_types()

        """ This is just so that the image and palette will be loaded"""
        sprite, _ = self.sprite_manager.create(SPRITE_WHITE_LINE_x5)
        #
        # self.shift_palette = sprite_manager.sprite_palettes[SPRITE_WHITE_LINE_x5]
        #
        # self.rotation = (
        #     (255, 0, 0),
        #     (255, 255, 0),
        #     (255, 0, 255),
        #     (0, 255, 255),
        #     (0, 255, 0),
        #     (0, 0, 255))
        # self.rot_index = 0
        #
        # self.shift_palette.set_rgb(0, self.rotation[self.rot_index])

        line_height = 24

        self.wait(500)
        self.sequence([
            evt.multi([
                evt.spawn(SPRITE_WHITE_LINE_x5, lane=0, z=spawn_z),
                evt.spawn(SPRITE_WHITE_LINE_x5, lane=0, z=spawn_z, y=26),
                evt.spawn(SPRITE_WHITE_LINE_VERT_x6, lane=0, z=spawn_z),
                evt.wait(small_wait)],
                repeat=10),
            evt.wait(small_wait)
        ], repeat=1)

        # asyncio.create_task(self.rotate_palette())


    async def rotate_palette(self):
        self.rot_index = self.rot_index % len(self.rotation)
        rgb = self.rotation[self.rot_index]
        self.shift_palette.set_rgb(0, rgb)

        self.rot_index += 1
        await asyncio.sleep_ms(100)

    def load_types(self):
        mgr = self.sprite_manager
        # mgr.add_type(
        #     sprite_type=SPRITE_BARRIER_LEFT,
        #     sprite_class=WarningWall,
        #     speed=self.base_speed)
        #
        # mgr.add_type(
        #     sprite_type=SPRITE_BARRIER_LEFT_x2,
        #     sprite_class=WarningWall,
        #     speed=self.base_speed,
        #     repeats=2,
        #     repeat_spacing=24)
        #
        # mgr.add_type(
        #     sprite_type=SPRITE_BARRIER_RIGHT,
        #     sprite_class=WarningWall,
        #     image_path="/img/road_barrier_yellow_inv.bmp",
        #     speed=self.base_speed)
        #
        # mgr.add_type(
        #     sprite_type=SPRITE_BARRIER_RIGHT_x2,
        #     image_path="/img/road_barrier_yellow_inv.bmp",
        #     sprite_class=WarningWall,
        #     speed=self.base_speed,
        #     repeats=2,
        #     repeat_spacing=24)
        #
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

        # mgr.add_type(
        #     sprite_type=SPRITE_WHITE_LINE,
        #     image_path="/img/test_white_line.bmp",
        #     width=24,
        #     height=2,
        #     speed=self.base_speed)
        #
        mgr.add_type(
            sprite_type=SPRITE_WHITE_LINE_x5,
            sprite_class=WhiteLineX5,
            image_path="/img/test_white_line.bmp",
            width=24,
            height=2,
            repeats=5,
            repeat_spacing=26,
            speed=self.base_speed)
        #
        # mgr.add_type(
        #     sprite_type=SPRITE_WHITE_LINE_VERT,
        #     image_path="/img/test_white_line_vert.bmp",
        #     width=2,
        #     height=24,
        #     speed=self.base_speed)

        mgr.add_type(
            sprite_type=SPRITE_WHITE_LINE_VERT_x6,
            image_path="/img/test_white_line_vert.bmp",
            width=2,
            height=24,
            repeats=6,
            repeat_spacing=26,
            speed=self.base_speed)


