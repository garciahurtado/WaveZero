import utime

from scaled_sprite import ScaledSprite
from sprite_pool import SpritePool
from stages.events import EventChain, WaitEvent, SpawnEnemyEvent, MultiEvent


class Stage1:
    started_ms: int
    event_chain: EventChain
    sprites: [] = []
    sprites_pool: [] = []
    enemies = None
    camera: None
    road_grid: None
    start_z: int = 2000

    def __init__(self, camera, lane_width=0, enemies=None):

        self.camera = camera
        self.lane_width = lane_width
        self.enemies = enemies
        self.speed = -1

        """ Init sprite pools """
        self.sprites = []
        base_sprite = ScaledSprite(
            filename="/img/road_barrier_yellow.bmp",
            frame_width=20,
            frame_height=15,
            lane_width=self.lane_width,
        )
        self.sprites_pool = SpritePool(size=30, camera=camera, lane_width=lane_width, base_sprite=base_sprite)
        self.event_chain = EventChain()

        """ lane numbers are 0-4"""
        wall_wait = 1500
        all_events = [
            WaitEvent(wall_wait),
            MultiEvent([
                self.spawn_one(lane=0),
                self.spawn_one(lane=1),
                self.spawn_one(lane=3),
                self.spawn_one(lane=4),
            ]),
            WaitEvent(wall_wait),
            MultiEvent([
                self.spawn_one(lane=0),
                self.spawn_one(lane=1),
                self.spawn_one(lane=3),
                self.spawn_one(lane=4),
            ]),
            WaitEvent(wall_wait),
            MultiEvent([
                self.spawn_one(lane=0),
                self.spawn_one(lane=1),
                self.spawn_one(lane=3),
                self.spawn_one(lane=4),
            ]),
            WaitEvent(wall_wait),
            MultiEvent([
                self.spawn_one(lane=0),
                self.spawn_one(lane=1),
                self.spawn_one(lane=3),
                self.spawn_one(lane=4),
            ]),
            WaitEvent(wall_wait),
            MultiEvent([
                self.spawn_one(lane=0),
                self.spawn_one(lane=1),
                self.spawn_one(lane=3),
                self.spawn_one(lane=4),
            ]),
            WaitEvent(wall_wait),
            MultiEvent([
                self.spawn_one(lane=0),
                self.spawn_one(lane=1),
                self.spawn_one(lane=3),
                self.spawn_one(lane=4),
            ]),

            WaitEvent(2000),
            self.spawn_one(lane=0),
            WaitEvent(1000),
            self.spawn_one(lane=4),
            WaitEvent(1000),
            self.spawn_one(lane=0),
            WaitEvent(1000),
            self.spawn_one(lane=4),
            WaitEvent(5000),

            MultiEvent([
                self.spawn_one(lane=0),
                self.spawn_one(lane=1),
                self.spawn_one(lane=3),
                self.spawn_one(lane=4),
                ]),

            WaitEvent(2000),
            MultiEvent([
                self.spawn_one(lane=1),
                self.spawn_one(lane=2),
                self.spawn_one(lane=3),
                self.spawn_one(lane=4),
            ]),
            WaitEvent(2000),
            MultiEvent([
                self.spawn_one(lane=0),
                self.spawn_one(lane=1),
                self.spawn_one(lane=2),
                self.spawn_one(lane=3),
            ]),
        ]

        for event in all_events:
            self.event_chain.add(event)
    def spawn_one(self, lane=0):
        return SpawnEnemyEvent(
            self.sprites_pool,
            self.sprites,
            lane=lane,
            z=self.start_z,
            speed=self.speed,
            enemy_pool=self.enemies)

    def start(self):
        self.started_ms = utime.ticks_ms()
        self.event_chain.start()

    def update(self, ellapsed):
        for sprite in self.sprites:
            sprite.update(ellapsed)

            if sprite.z < self.camera.min_z:
                sprite.kill()
                self.sprites.remove(sprite)
                self.enemies.remove(sprite)
                self.sprites_pool.add(sprite)


