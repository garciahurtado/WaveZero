import utime

from scaled_sprite import ScaledSprite
from sprite_pool import SpritePool
from stages.events import EventChain, WaitEvent, SpawnEnemyEvent


class Stage1:
    started_ms: int
    event_chain: EventChain
    sprites: [] = []
    sprites_pool: [] = []
    camera: None
    road_grid: None

    def __init__(self, camera, lane_width=0):
        self.camera = camera
        self.lane_width = lane_width

        """ Init sprite pools """
        self.sprites = []
        base_sprite = ScaledSprite(
            filename="/img/road_barrier_yellow.bmp",
            frame_width=20,
            frame_height=15,
            lane_width=self.lane_width,
        )
        self.sprites_pool = SpritePool(size=0, camera=camera, lane_width=lane_width, base_sprite=base_sprite)
        self.event_chain = EventChain()
        start_z = 2000

        """ lane numbers are 0-4"""

        speed = -10
        all_events = [
            WaitEvent(2000),
            SpawnEnemyEvent(
                self.sprites_pool,
                self.sprites,
                lane=0,
                z=start_z,
                speed=speed),
            WaitEvent(1000),
            SpawnEnemyEvent(
                self.sprites_pool,
                self.sprites,
                lane=4,
                z=start_z,
                speed=speed),
            WaitEvent(1000),
            SpawnEnemyEvent(
                self.sprites_pool,
                self.sprites,
                lane=0,
                z=start_z,
                speed=speed),
            WaitEvent(1000),
            SpawnEnemyEvent(
                self.sprites_pool,
                self.sprites,
                lane=4,
                z=start_z,
                speed=speed),
            WaitEvent(5000),

            SpawnEnemyEvent(
                self.sprites_pool,
                self.sprites,
                lane=0,
                z=start_z,
                speed=speed),
            SpawnEnemyEvent(
                self.sprites_pool,
                self.sprites,
                lane=1,
                z=start_z,
                speed=speed),
            SpawnEnemyEvent(
                self.sprites_pool,
                self.sprites,
                lane=2,
                z=start_z,
                speed=speed),
            SpawnEnemyEvent(
                self.sprites_pool,
                self.sprites,
                lane=3,
                z=start_z,
                speed=speed),
            SpawnEnemyEvent(
                self.sprites_pool,
                self.sprites,
                lane=4,
                z=start_z,
                speed=speed),
        ]

        for event in all_events:
            self.event_chain.add(event)

    def start(self):
        self.started_ms = utime.ticks_ms()
        self.event_chain.start()

    def update(self):
        for sprite in self.sprites:
            sprite.update()
