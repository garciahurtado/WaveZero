# from anim.palette_rotate import PaletteRotate
import gc

from profiler import timed
from sprites.flying_tri import FlyingTri
from sprites.sprite_pool import SpritePool

import utime

from sprites.road_barrier import RoadBarrier
from stages.events import EventChain, WaitEvent, SpawnEnemyEvent, MultiEvent

class Stage1:
    started_ms: int
    event_chain: EventChain
    sprites: [] = []
    sprites_pool = None
    sprites_pool_tris = None
    camera: None
    road_grid: None
    speed: int = 0
    lane_width: int = 0

    def __init__(self, camera, lane_width=0, speed=None):
        self.sprites = []
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

        self.sprites_pool_tris = SpritePool(
            size=20,
            camera=camera,
            base_sprite=sprite_tri,
            active_sprites=self.sprites)

        # sprite_barrier.set_alpha(0)
        self.sprites_pool = SpritePool(
            size=20,
            camera=camera,
            base_sprite=sprite_barrier,
            active_sprites=self.sprites)

        self.event_chain = EventChain(self.speed)


        """ Main Level Content ---------------------------------------------------- """

        """ lane numbers are 0-4"""
        # wall_wait = 2000
        spawn_z = 800
        wall_wait = 200
        all_events = [
            WaitEvent(wall_wait),
            self.spawn_one(lane=0, dead_pool=self.sprites_pool, z=spawn_z),
            self.spawn_one(lane=1, dead_pool=self.sprites_pool, z=spawn_z),
            self.spawn_one(lane=3, dead_pool=self.sprites_pool, z=spawn_z),
            self.spawn_one(lane=4, dead_pool=self.sprites_pool, z=spawn_z),
            WaitEvent(wall_wait * 2),

            self.spawn_one(lane=1, dead_pool=self.sprites_pool_tris, z=spawn_z),
            self.spawn_one(lane=2, dead_pool=self.sprites_pool_tris, z=spawn_z),
            WaitEvent(wall_wait),
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

        for event in all_events:
            self.event_chain.add(event)

    def spawn_one(self, lane=0, dead_pool=None, z=1500):
        """ Event factory method, doesn't actually spawn enemies """

        if not dead_pool:
            dead_pool = self.sprites_pool

        return SpawnEnemyEvent(
            lane=lane,
            z=z,
            dead_pool=dead_pool,
            )

    def start(self):
        print("STARTED")
        self.started_ms = utime.ticks_ms()
        self.event_chain.start()

    def update(self, elapsed):
        # print(f"Sprite pools: 1:{len(self.sprites_pool)} / 2:{len(self.sprites_pool_tris)}")

        self.sprites_pool.update(elapsed)
        self.sprites_pool_tris.update(elapsed)

    def update_frames(self):
        for sprite in self.sprites:
            sprite.update_frame()

    def show(self, display):
        self.sprites_pool.show(display)
        self.sprites_pool_tris.show(display)



