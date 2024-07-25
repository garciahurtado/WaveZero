# from anim.palette_rotate import PaletteRotate
import gc

from profiler import timed
from sprites.PlasmaCircle import PlasmaCircle
from sprites.flying_tri import FlyingTri
from sprites.sprite_pool import SpritePool

import utime

from sprites.road_barrier import RoadBarrier
from stages.events import EventChain, WaitEvent, SpawnEnemyEvent, MultiEvent

class Stage1:
    started_ms: int
    event_chain: EventChain
    sprites: [] = []
    sprites_pool_barrier = None
    sprites_pool_tris = None
    sprites_pool_circles = None
    camera: None
    road_grid: None
    speed: int = 0
    lane_width: int = 0

    def __init__(self, camera, lane_width=0, speed=None):
        self.camera = camera
        self.lane_width = lane_width
        self.speed = speed

        gc.collect()
        print("Creating sprite pools....")

        """ Init sprites """

        self.sprites = []
        sprite_tri = FlyingTri(
            filename="/img/laser_tri.bmp",
            lane_width=self.lane_width
        )

        sprite_barrier = RoadBarrier(
            filename="/img/road_barrier_yellow.bmp",
            lane_width=self.lane_width
        )
        sprite_barrier_inv = RoadBarrier(
            filename="/img/road_barrier_yellow_inv.bmp",
            lane_width=self.lane_width
        )

        plasma_circle = PlasmaCircle(
            lane_width=self.lane_width
        )

        # sprite_barrier = ScaledSprite(
        #     filename="/img/road_wall_single.bmp",
        #     frame_width=12,
        #     frame_height=22,
        #     lane_width=self.lane_width,
        #     horiz_z=self.sprite_max_z,
        #     z=100
        # )

        """ Rotate palette animation """
        fps = 120
        # self.color_anim = PaletteRotate(sprite_barrier.palette, 1000 / fps, slice=[1, 2])
        # loop = asyncio.get_event_loop()
        # loop.create_task(self.color_anim.run(fps=fps))

        """ Sprite pools """

        self.sprites_pool_barrier = SpritePool(
            size=50,
            camera=camera,
            base_sprite=sprite_barrier,
            active_sprites=self.sprites)

        self.sprites_pool_barrier_inv = SpritePool(
            size=50,
            camera=camera,
            base_sprite=sprite_barrier_inv,
            active_sprites=self.sprites)

        self.sprites_pool_tris = SpritePool(
            size=1,
            camera=camera,
            base_sprite=sprite_tri,
            active_sprites=self.sprites)

        self.sprites_pool_circles = SpritePool(
            size=1,
            camera=camera,
            base_sprite=plasma_circle,
            active_sprites=self.sprites)


        self.event_chain = EventChain()


        """ Main Level Content ---------------------------------------------------- """

        """ lane numbers are 0-4"""
        # wall_wait = 2000
        spawn_z = 1500
        wall_wait = 2000
        all_events = [

            MultiEvent([
                self.spawn_one(lane=0, dead_pool=self.sprites_pool_barrier_inv, z=spawn_z),
                self.spawn_one(lane=1, dead_pool=self.sprites_pool_barrier_inv, z=spawn_z),
                self.spawn_one(lane=3, dead_pool=self.sprites_pool_barrier, z=spawn_z),
                self.spawn_one(lane=4, dead_pool=self.sprites_pool_barrier, z=spawn_z),
                WaitEvent(wall_wait),
            ], times=3),
            MultiEvent([
                self.spawn_one(lane=0, dead_pool=self.sprites_pool_barrier_inv, z=spawn_z),
                self.spawn_one(lane=1, dead_pool=self.sprites_pool_barrier_inv, z=spawn_z),
                self.spawn_one(lane=3, dead_pool=self.sprites_pool_barrier, z=spawn_z),
                self.spawn_one(lane=4, dead_pool=self.sprites_pool_barrier, z=spawn_z),
                WaitEvent(wall_wait/2),
            ], times=3),
            MultiEvent([
                self.spawn_one(lane=0, dead_pool=self.sprites_pool_barrier_inv, z=spawn_z),
                self.spawn_one(lane=1, dead_pool=self.sprites_pool_barrier_inv, z=spawn_z),
                self.spawn_one(lane=3, dead_pool=self.sprites_pool_barrier, z=spawn_z),
                self.spawn_one(lane=4, dead_pool=self.sprites_pool_barrier, z=spawn_z),
                WaitEvent(wall_wait / 4),
            ], times=3),
            WaitEvent(wall_wait),
            MultiEvent([
                self.spawn_one(lane=0, dead_pool=self.sprites_pool_barrier_inv, z=spawn_z),
                self.spawn_one(lane=1, dead_pool=self.sprites_pool_barrier_inv, z=spawn_z),
                self.spawn_one(lane=3, dead_pool=self.sprites_pool_barrier, z=spawn_z),
                self.spawn_one(lane=4, dead_pool=self.sprites_pool_barrier, z=spawn_z),
                WaitEvent(wall_wait / 2),
            ]),
            MultiEvent([
                self.spawn_one(lane=0, dead_pool=self.sprites_pool_barrier_inv, z=spawn_z),
                self.spawn_one(lane=2, dead_pool=self.sprites_pool_barrier, z=spawn_z),
                self.spawn_one(lane=3, dead_pool=self.sprites_pool_barrier, z=spawn_z),
                self.spawn_one(lane=4, dead_pool=self.sprites_pool_barrier, z=spawn_z),
                WaitEvent(wall_wait / 2),
            ]),
            MultiEvent([
                self.spawn_one(lane=1, dead_pool=self.sprites_pool_barrier, z=spawn_z),
                self.spawn_one(lane=2, dead_pool=self.sprites_pool_barrier, z=spawn_z),
                self.spawn_one(lane=3, dead_pool=self.sprites_pool_barrier, z=spawn_z),
                self.spawn_one(lane=4, dead_pool=self.sprites_pool_barrier, z=spawn_z),
                WaitEvent(wall_wait / 2),
            ]),
            MultiEvent([
                self.spawn_one(lane=0, dead_pool=self.sprites_pool_barrier_inv, z=spawn_z),
                self.spawn_one(lane=2, dead_pool=self.sprites_pool_barrier, z=spawn_z),
                self.spawn_one(lane=3, dead_pool=self.sprites_pool_barrier, z=spawn_z),
                self.spawn_one(lane=4, dead_pool=self.sprites_pool_barrier, z=spawn_z),
                WaitEvent(wall_wait / 2),
            ]),
            MultiEvent([
                self.spawn_one(lane=0, dead_pool=self.sprites_pool_barrier_inv, z=spawn_z),
                self.spawn_one(lane=1, dead_pool=self.sprites_pool_barrier_inv, z=spawn_z),
                self.spawn_one(lane=3, dead_pool=self.sprites_pool_barrier, z=spawn_z),
                self.spawn_one(lane=4, dead_pool=self.sprites_pool_barrier, z=spawn_z),
                WaitEvent(wall_wait / 2),
            ]),
            MultiEvent([
                self.spawn_one(lane=0, dead_pool=self.sprites_pool_barrier_inv, z=spawn_z),
                self.spawn_one(lane=1, dead_pool=self.sprites_pool_barrier_inv, z=spawn_z),
                self.spawn_one(lane=2, dead_pool=self.sprites_pool_barrier_inv, z=spawn_z),
                self.spawn_one(lane=4, dead_pool=self.sprites_pool_barrier, z=spawn_z),
                WaitEvent(wall_wait / 2),
            ]),
            MultiEvent([
                self.spawn_one(lane=0, dead_pool=self.sprites_pool_barrier_inv, z=spawn_z),
                self.spawn_one(lane=1, dead_pool=self.sprites_pool_barrier_inv, z=spawn_z),
                self.spawn_one(lane=2, dead_pool=self.sprites_pool_barrier_inv, z=spawn_z),
                self.spawn_one(lane=3, dead_pool=self.sprites_pool_barrier_inv, z=spawn_z),
                WaitEvent(wall_wait / 2),
            ]),
            MultiEvent([
                self.spawn_one(lane=0, dead_pool=self.sprites_pool_barrier_inv, z=spawn_z),
                self.spawn_one(lane=1, dead_pool=self.sprites_pool_barrier_inv, z=spawn_z),
                self.spawn_one(lane=2, dead_pool=self.sprites_pool_barrier_inv, z=spawn_z),
                self.spawn_one(lane=4, dead_pool=self.sprites_pool_barrier, z=spawn_z),
                WaitEvent(wall_wait / 2),
            ]),
            MultiEvent([
                self.spawn_one(lane=0, dead_pool=self.sprites_pool_barrier_inv, z=spawn_z),
                self.spawn_one(lane=1, dead_pool=self.sprites_pool_barrier_inv, z=spawn_z),
                self.spawn_one(lane=3, dead_pool=self.sprites_pool_barrier, z=spawn_z),
                self.spawn_one(lane=4, dead_pool=self.sprites_pool_barrier, z=spawn_z),
                WaitEvent(wall_wait / 2),
            ]),

            #
            # WaitEvent(wall_wait),
            # MultiEvent([
            #     self.spawn_one(lane=0, dead_pool=self.sprites_pool_barrier, z=spawn_z),
            #     self.spawn_one(lane=1, dead_pool=self.sprites_pool_barrier, z=spawn_z),
            #     self.spawn_one(lane=3, dead_pool=self.sprites_pool_barrier, z=spawn_z),
            #     self.spawn_one(lane=4, dead_pool=self.sprites_pool_barrier, z=spawn_z),
            # ]),
            #
            # WaitEvent(wall_wait),
            # MultiEvent([
            #     self.spawn_one(lane=0, dead_pool=self.sprites_pool_barrier, z=spawn_z),
            #     self.spawn_one(lane=1, dead_pool=self.sprites_pool_barrier, z=spawn_z),
            #     self.spawn_one(lane=3, dead_pool=self.sprites_pool_barrier, z=spawn_z),
            #     self.spawn_one(lane=4, dead_pool=self.sprites_pool_barrier, z=spawn_z),
            # ]),
            #
            # WaitEvent(wall_wait),
            # MultiEvent([
            #     self.spawn_one(lane=0, dead_pool=self.sprites_pool_barrier, z=spawn_z),
            #     self.spawn_one(lane=1, dead_pool=self.sprites_pool_barrier, z=spawn_z),
            #     self.spawn_one(lane=3, dead_pool=self.sprites_pool_barrier, z=spawn_z),
            #     self.spawn_one(lane=4, dead_pool=self.sprites_pool_barrier, z=spawn_z),
            # ]),
            #
            # WaitEvent(wall_wait),
            # MultiEvent([
            #     self.spawn_one(lane=0, dead_pool=self.sprites_pool_barrier, z=spawn_z),
            #     self.spawn_one(lane=1, dead_pool=self.sprites_pool_barrier, z=spawn_z),
            #     self.spawn_one(lane=3, dead_pool=self.sprites_pool_barrier, z=spawn_z),
            #     self.spawn_one(lane=4, dead_pool=self.sprites_pool_barrier, z=spawn_z),
            # ]),
            #
            # WaitEvent(wall_wait),
            # MultiEvent([
            #     self.spawn_one(lane=0, dead_pool=self.sprites_pool_barrier, z=spawn_z),
            #     self.spawn_one(lane=1, dead_pool=self.sprites_pool_barrier, z=spawn_z),
            #     self.spawn_one(lane=3, dead_pool=self.sprites_pool_barrier, z=spawn_z),
            #     self.spawn_one(lane=4, dead_pool=self.sprites_pool_barrier, z=spawn_z),
            # ]),
            #
            # WaitEvent(wall_wait),
            # MultiEvent([
            #     self.spawn_one(lane=0, dead_pool=self.sprites_pool_barrier, z=spawn_z),
            #     self.spawn_one(lane=1, dead_pool=self.sprites_pool_barrier, z=spawn_z),
            #     self.spawn_one(lane=3, dead_pool=self.sprites_pool_barrier, z=spawn_z),
            #     self.spawn_one(lane=4, dead_pool=self.sprites_pool_barrier, z=spawn_z),
            # ]),
            #
            # WaitEvent(wall_wait),
            # self.spawn_one(lane=0, dead_pool=self.sprites_pool_circles, z=spawn_z),
            # self.spawn_one(lane=1, dead_pool=self.sprites_pool_circles, z=spawn_z),
            # self.spawn_one(lane=3, dead_pool=self.sprites_pool_circles, z=spawn_z),
            # self.spawn_one(lane=4, dead_pool=self.sprites_pool_circles, z=spawn_z),
            #
            # WaitEvent(wall_wait),
            # self.spawn_one(lane=2, dead_pool=self.sprites_pool_circles, z=spawn_z),
            #
            # WaitEvent(wall_wait),
            # self.spawn_one(lane=0, dead_pool=self.sprites_pool_circles, z=spawn_z),
            # self.spawn_one(lane=1, dead_pool=self.sprites_pool_circles, z=spawn_z),
            # self.spawn_one(lane=2, dead_pool=self.sprites_pool_circles, z=spawn_z),
            # self.spawn_one(lane=3, dead_pool=self.sprites_pool_circles, z=spawn_z),
            # self.spawn_one(lane=4, dead_pool=self.sprites_pool_circles, z=spawn_z),
            #
            # WaitEvent(wall_wait),
            # self.spawn_one(lane=0, dead_pool=self.sprites_pool_circles, z=spawn_z),
            # self.spawn_one(lane=1, dead_pool=self.sprites_pool_circles, z=spawn_z),
            # self.spawn_one(lane=2, dead_pool=self.sprites_pool_circles, z=spawn_z),
            # self.spawn_one(lane=3, dead_pool=self.sprites_pool_circles, z=spawn_z),
            # self.spawn_one(lane=4, dead_pool=self.sprites_pool_circles, z=spawn_z),
            #
            # WaitEvent(wall_wait),
            # self.spawn_one(lane=0, dead_pool=self.sprites_pool_circles, z=spawn_z),
            # self.spawn_one(lane=1, dead_pool=self.sprites_pool_circles, z=spawn_z),
            # self.spawn_one(lane=2, dead_pool=self.sprites_pool_circles, z=spawn_z),
            # self.spawn_one(lane=3, dead_pool=self.sprites_pool_circles, z=spawn_z),
            # self.spawn_one(lane=4, dead_pool=self.sprites_pool_circles, z=spawn_z),
            #
            # WaitEvent(wall_wait),
            # self.spawn_one(lane=0, dead_pool=self.sprites_pool_circles, z=spawn_z),
            # self.spawn_one(lane=1, dead_pool=self.sprites_pool_circles, z=spawn_z),
            # self.spawn_one(lane=2, dead_pool=self.sprites_pool_circles, z=spawn_z),
            # self.spawn_one(lane=3, dead_pool=self.sprites_pool_circles, z=spawn_z),
            # self.spawn_one(lane=4, dead_pool=self.sprites_pool_circles, z=spawn_z),

            # self.spawn_one(lane=0, dead_pool=self.sprites_pool, z=spawn_z),
            # self.spawn_one(lane=1, dead_pool=self.sprites_pool, z=spawn_z),
            # self.spawn_one(lane=3, dead_pool=self.sprites_pool, z=spawn_z),
            # self.spawn_one(lane=4, dead_pool=self.sprites_pool, z=spawn_z),
            # WaitEvent(wall_wait * 2),
            #
            # self.spawn_one(lane=1, dead_pool=self.sprites_pool_tris, z=spawn_z),
            # self.spawn_one(lane=2, dead_pool=self.sprites_pool_tris, z=spawn_z),
            # WaitEvent(wall_wait),
            #
            # self.spawn_one(lane=0, dead_pool=self.sprites_pool_tris),
            # self.spawn_one(lane=4, dead_pool=self.sprites_pool_tris),
            # WaitEvent(200),
            #

            # MultiEvent([
            #     self.spawn_one(lane=0),
            #     self.spawn_one(lane=1),
            #     self.spawn_one(lane=3),
            #     self.spawn_one(lane=4),
            # ]),
            # WaitEvent(wall_wait),
            # MultiEvent([
            #     self.spawn_one(lane=0),
            #     self.spawn_one(lane=1),
            #     self.spawn_one(lane=3),
            #     self.spawn_one(lane=4),
            # ]),
            # WaitEvent(wall_wait),
            # MultiEvent([
            #     self.spawn_one(lane=0),
            #     self.spawn_one(lane=1),
            #     self.spawn_one(lane=3),
            #     self.spawn_one(lane=4),
            # ]),
            #
            # WaitEvent(2000),
            # self.spawn_one(lane=0),
            # WaitEvent(1000),
            # self.spawn_one(lane=4),
            # WaitEvent(1000),
            # self.spawn_one(lane=0),
            # WaitEvent(1000),
            # self.spawn_one(lane=4),
            # WaitEvent(5000),
            #
            # MultiEvent([
            #     self.spawn_one(lane=0),
            #     self.spawn_one(lane=1),
            #     self.spawn_one(lane=3),
            #     self.spawn_one(lane=4),
            #     ]),
            #
            # WaitEvent(2000),
            # MultiEvent([
            #     self.spawn_one(lane=1),
            #     self.spawn_one(lane=2),
            #     self.spawn_one(lane=3),
            #     self.spawn_one(lane=4),
            # ]),
            # WaitEvent(2000),
            # MultiEvent([
            #     self.spawn_one(lane=0),
            #     self.spawn_one(lane=1),
            #     self.spawn_one(lane=2),
            #     self.spawn_one(lane=3),
            # ]),
        ]

        self.event_chain.add_many(all_events)

    def spawn_one(self, lane=0, dead_pool=None, z=1500):
        """ Event factory method, doesn't actually spawn enemies """

        return SpawnEnemyEvent(
            lane=lane,
            z=z,
            dead_pool=dead_pool,
            )

    def start(self):
        gc.collect()
        self.started_ms = utime.ticks_ms()
        self.event_chain.start()

    def update(self, elapsed):
        # print(f"Sprite pools: 1:{len(self.sprites_pool)} / 2:{len(self.sprites_pool_tris)}")
        self.event_chain.update()
        self.sprites_pool_barrier.update(elapsed)
        self.sprites_pool_tris.update(elapsed)
        self.sprites_pool_circles.update(elapsed)

    def show(self, display):
        self.sprites_pool_barrier.show(display)
        self.sprites_pool_tris.show(display)
        self.sprites_pool_circles.show(display)



