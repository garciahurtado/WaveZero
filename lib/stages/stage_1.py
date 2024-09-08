from sprites2.laser_wall import LaserWall
from sprites2.warning_wall import WarningWall
from stages.events import Event
from stages.stage import Stage
from sprites2.sprite_types import *


class Stage1(Stage):
    base_speed = -100

    def __init__(self, sprite_manager):
        super().__init__(sprite_manager)

        spawn_z = 800
        small_wait = 2000
        tiny_wait = 100

        Event.sprite_manager = sprite_manager
        evt = self.events

        self.load_types()

        """ This is just so that the image and palette will be loaded"""
        sprite, _ = self.sprite_manager.create(SPRITE_WHITE_LINE_VERT_x6)
        sprite.visible = False
        sprite.active = False

        print(sprite_manager.sprite_palettes)
        shift_palette = sprite_manager.sprite_palettes[SPRITE_WHITE_LINE_VERT_x6]
        # shift_palette.set_int(1, 0xCC0000)

        self.wait(500)
        self.sequence([
            evt.spawn(SPRITE_WHITE_LINE_x5, lane=0, z=spawn_z),
            evt.wait(tiny_wait),
            evt.spawn(SPRITE_WHITE_LINE_x5, lane=0, z=spawn_z),
            evt.wait(tiny_wait),
            evt.spawn(SPRITE_WHITE_LINE_x5, lane=0, z=spawn_z),
            evt.wait(tiny_wait),
            evt.spawn(SPRITE_WHITE_LINE_x5, lane=0, z=spawn_z),
            evt.wait(tiny_wait),
            evt.spawn(SPRITE_WHITE_LINE_x5, lane=0, z=spawn_z),
            evt.wait(tiny_wait),
            evt.spawn(SPRITE_WHITE_LINE_x5, lane=0, z=spawn_z),
            evt.wait(tiny_wait),
            evt.spawn(SPRITE_WHITE_LINE_x5, lane=0, z=spawn_z),
            evt.wait(tiny_wait),
            evt.spawn(SPRITE_WHITE_LINE_x5, lane=0, z=spawn_z),
            evt.wait(tiny_wait),
            evt.spawn(SPRITE_WHITE_LINE_x5, lane=0, z=spawn_z),
            evt.wait(tiny_wait),
            evt.spawn(SPRITE_WHITE_LINE_x5, lane=0, z=spawn_z),
            evt.wait(tiny_wait),
            evt.wait(small_wait),

            # evt.spawn(SPRITE_WHITE_LINE_VERT, lane=2, z=spawn_z),
            # evt.spawn(SPRITE_WHITE_LINE_VERT, lane=3, z=spawn_z),
            # evt.spawn(SPRITE_WHITE_LINE_VERT, lane=4, z=spawn_z),
            # evt.spawn(SPRITE_WHITE_LINE_VERT, lane=5, z=spawn_z),
            # evt.spawn(SPRITE_WHITE_LINE_x5, x=0, y=1, z=spawn_z, lane=0),
            # evt.spawn(SPRITE_WHITE_LINE_x5, lane=0, z=spawn_z, y=26),
            # evt.spawn(SPRITE_WHITE_LINE_x5, lane=0, z=spawn_z, y=26),
            # evt.spawn(SPRITE_WHITE_LINE, lane=1, z=spawn_z),
            # evt.wait(small_wait),
            # evt.spawn(SPRITE_WHITE_LINE, lane=2, z=spawn_z),
            # evt.wait(small_wait),
            # evt.spawn(SPRITE_WHITE_LINE, lane=3, z=spawn_z),
            # evt.wait(small_wait),
            # evt.spawn(SPRITE_WHITE_LINE, lane=4, z=spawn_z),
            # evt.wait(small_wait),
            # evt.spawn(SPRITE_WHITE_LINE, lane=3, z=spawn_z),
            # evt.wait(small_wait),
            # evt.spawn(SPRITE_WHITE_LINE, lane=2, z=spawn_z),
            # evt.wait(small_wait),
            # evt.spawn(SPRITE_WHITE_LINE, lane=1, z=spawn_z),
            # evt.wait(small_wait),
            # evt.spawn(SPRITE_WHITE_LINE, lane=0, z=spawn_z),
            # evt.wait(small_wait),

            # evt.wait(tiny_wait),
            # evt.spawn(SPRITE_BARRIER_RIGHT_x2, lane=0, z=spawn_z),
            # evt.spawn(SPRITE_BARRIER_LEFT_x2, lane=3, z=spawn_z),
            # evt.wait(tiny_wait),
            # evt.spawn(SPRITE_LASER_WALL_x2, lane=0, z=spawn_z),
            # evt.spawn(SPRITE_LASER_WALL_x2, lane=3, z=spawn_z),
            # evt.wait(tiny_wait)
        ], repeat=4)

        # .wait(small_wait)
        # .wait(small_wait)
        # .wait(small_wait))
        # .spawn(SPRITE_LASER_WALL_x2, lane=0, z=spawn_z)
        # .spawn(SPRITE_LASER_WALL_x2, lane=3, z=spawn_z).wait(100)
        # .spawn(SPRITE_LASER_WALL_x2, lane=0, z=spawn_z)
        # .spawn(SPRITE_LASER_WALL_x2, lane=3, z=spawn_z).wait(100)
        # .spawn(SPRITE_LASER_WALL_x2, lane=0, z=spawn_z)
        # .spawn(SPRITE_LASER_WALL_x2, lane=3, z=spawn_z).wait(100)
        # .spawn(SPRITE_LASER_WALL_x2, lane=0, z=spawn_z)
        # .spawn(SPRITE_LASER_WALL_x2, lane=3, z=spawn_z).wait(100)
        # .spawn(SPRITE_LASER_WALL_x2, lane=0, z=spawn_z)
        # .spawn(SPRITE_LASER_WALL_x2, lane=3, z=spawn_z).wait(100)
        # .spawn(SPRITE_LASER_WALL_x2, lane=0, z=spawn_z)
        # .spawn(SPRITE_LASER_WALL_x2, lane=3, z=spawn_z).wait(100)
        # .spawn(SPRITE_LASER_WALL_x5, lane=3, z=spawn_z).wait(100))

        # self.multi(self
        #            .spawn(SPRITE_BARRIER_LEFT, lane=0, z=spawn_z)
        #            .spawn(SPRITE_BARRIER_LEFT, lane=1, z=spawn_z)
        #            .spawn(SPRITE_BARRIER_LEFT, lane=3, z=spawn_z)
        #            .spawn(SPRITE_BARRIER_LEFT, lane=4, z=spawn_z)
        #            )

        # self.multi(self\
        #         .spawn(SPRITE_BARRIER_LEFT, lane=0, z=spawn_z)
        #         .spawn(SPRITE_BARRIER_LEFT, lane=1, z=spawn_z)
        #         .spawn(SPRITE_BARRIER_LEFT, lane=3, z=spawn_z)
        #         .spawn(SPRITE_BARRIER_LEFT, lane=4, z=spawn_z)
        #         .wait(small_wait),
        #         repeat=3)\
        #         .wait(small_wait)\
        #         .multi(
        #             spawn("tri", lane=1, z=spawn_z),
        #             spawn("tri", lane=2, z=spawn_z),
        #             wait(small_wait),
        #         )

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

        mgr.add_type(
            sprite_type=SPRITE_LASER_WALL,
            sprite_class=LaserWall,
            speed=self.base_speed)

        mgr.add_type(
            sprite_type=SPRITE_LASER_WALL_x2,
            sprite_class=LaserWall,
            repeats=2,
            repeat_spacing=24)

        mgr.add_type(
            sprite_type=SPRITE_LASER_WALL_x5,
            sprite_class=LaserWall,
            repeats=5,
            repeat_spacing=24)

        mgr.add_type(
            sprite_type=SPRITE_WHITE_LINE,
            image_path="/img/test_white_line.bmp",
            width=24,
            height=2,
            speed=self.base_speed)

        mgr.add_type(
            sprite_type=SPRITE_WHITE_LINE_x5,
            image_path="/img/test_white_line.bmp",
            width=24,
            stretch_width=28,
            height=2,
            repeats=5,
            repeat_spacing=27,
            speed=self.base_speed)


        mgr.add_type(
            sprite_type=SPRITE_WHITE_LINE_VERT,
            image_path="/img/test_white_line_vert.bmp",
            width=2,
            height=24,
            speed=self.base_speed)

        mgr.add_type(
            sprite_type=SPRITE_WHITE_LINE_VERT_x6,
            image_path="/img/test_white_line_vert.bmp",
            width=2,
            height=24,
            repeats=6,
            repeat_spacing=28, # <=
            speed=self.base_speed)


