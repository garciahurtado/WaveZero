from sprites2.laser_wall import LaserWall
from sprites2.warning_wall import WarningWall
from stages.stage import Stage
from sprites2.sprite_types import *

class Stage1(Stage):
    base_speed = -50

    def __init__(self, sprite_manager):
        super().__init__(sprite_manager)

        spawn_z = 400
        small_wait = 2000

        self.load_types()
        self.spawn(SPRITE_LASER_WALL, lane=0, z=spawn_z)
        self.wait(small_wait)

        self.spawn(SPRITE_LASER_WALL, lane=1, z=spawn_z)
        self.wait(small_wait)

        self.spawn(SPRITE_LASER_WALL, lane=2, z=spawn_z)
        self.wait(small_wait)

        self.spawn(SPRITE_LASER_WALL, lane=3, z=spawn_z)
        self.wait(small_wait)

        self.spawn(SPRITE_LASER_WALL, lane=4, z=spawn_z)
        self.wait(small_wait)

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
        self.sprite_manager.add_type(SPRITE_BARRIER_LEFT, WarningWall, "/img/road_barrier_yellow.bmp", self.base_speed,
                                     24, 15, 4)
        self.sprite_manager.add_type(SPRITE_BARRIER_LEFT_x2, WarningWall, "/img/road_barrier_yellow.bmp", self.base_speed,
                                     24, 15, 4,
                                     None, None, repeats=2, repeat_spacing=24)
        self.sprite_manager.add_type(SPRITE_BARRIER_RIGHT, WarningWall, "/img/road_barrier_yellow_inv.bmp",
                                     self.base_speed, 24, 15,
                                     4, None, None, repeats=2, repeat_spacing=24)
        self.sprite_manager.add_type(SPRITE_LASER_WALL, LaserWall, "/img/laser_wall.bmp", self.base_speed, 22, 10, 4,
                                     None, 0x000)
        self.sprite_manager.add_type(SPRITE_LASER_WALL_x2, LaserWall, "/img/laser_wall.bmp", self.base_speed, 22, 10, 4,
                                     None, 0x000,
                                     repeats=2, repeat_spacing=24)
