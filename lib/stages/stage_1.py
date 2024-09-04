from sprites2.laser_wall import LaserWall
from sprites2.warning_wall import WarningWall
from stages.events import Event
from stages.stage import Stage
from sprites2.sprite_types import *


class Stage1(Stage):
    base_speed = -50

    def __init__(self, sprite_manager):
        super().__init__(sprite_manager)

        spawn_z = 1500
        small_wait = 1000
        tiny_wait = 300

        Event.sprite_manager = sprite_manager
        evt = self.events

        self.load_types()
        self.wait(500)  # 28 sprites below
        self.multi([
            # evt.spawn(SPRITE_BARRIER_RIGHT_x2, lane=0, z=spawn_z),
            # evt.spawn(SPRITE_BARRIER_LEFT_x2, lane=3, z=spawn_z),
            # evt.wait(tiny_wait),
            evt.spawn(SPRITE_LASER_WALL_x2, lane=0, z=spawn_z),
            evt.spawn(SPRITE_LASER_WALL_x2, lane=3, z=spawn_z),
            evt.wait(tiny_wait)
        ], repeat=8)

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

        # mgr.add_type(SPRITE_BARRIER_LEFT_x2, WarningWall, "/img/road_barrier_yellow.bmp", self.base_speed,
        #                              24, 15, 4,
        #                              None, None, repeats=2, repeat_spacing=24)
        # mgr.add_type(SPRITE_BARRIER_RIGHT, WarningWall, "/img/road_barrier_yellow_inv.bmp",
        #                              self.base_speed, 24, 15, 4)
        # mgr.add_type(SPRITE_BARRIER_RIGHT_x2, WarningWall, "/img/road_barrier_yellow_inv.bmp",
        #                              self.base_speed, 24, 15, 4, None, None, repeats=2, repeat_spacing=24)
        #
        # mgr.add_type(SPRITE_LASER_WALL, LaserWall, "/img/laser_wall.bmp", self.base_speed, 24, 10, 4)
        # mgr.add_type(SPRITE_LASER_WALL_x2, LaserWall, "/img/laser_wall.bmp", self.base_speed, 24, 10, 4,
        #                              None, 0x000,
        #                              repeats=2, repeat_spacing=24)
        # mgr.add_type(SPRITE_LASER_WALL_x5, LaserWall, "/img/laser_wall.bmp", self.base_speed, 24, 10, 4,
        #                              None, 0x000,
        #                              repeats=5, repeat_spacing=24)
