import asyncio
import math

import utime
class Event:
    started_ms: int
    active: bool = False
    finished: bool = False
    next_event = False
    speed: int = 0
    elapsed = 0
    last_tick = 0

    def start(self):
        self.started_ms = utime.ticks_ms()
        self.active: True

    def update(self):
        """ Override and call from child classes """
        if not self.active:
            return False

        if not self.last_tick:
            self.last_tick = self.started_ms

        elapsed = utime.ticks_ms() - self.last_tick
        return elapsed

class EventChain:
    events: [] = []
    current_event: Event = None
    finished: bool = False
    running: bool = False
    fps: int = 0

    def start(self, fps=30):
        self.fps = fps
        self.running = True
        self.current_event = self.events[0]

        self.current_event.start()

        loop = asyncio.get_event_loop()
        loop.create_task(self.update())

    def reset(self):
        self.running = False
        self.current_event = self.events[0]
        # TODO: add task cancellation

    def add(self, new_event: Event):
        """ Chain it to the last event"""
        if len(self.events) > 0:
            last: Event = self.events[-1]
            last.next_event = new_event

        self.events.append(new_event)

    def add_many(self, all_events):
        for event in all_events:
            self.add(event)

    async def update(self):
        while self.running:
            if self.current_event.finished:
                if self.current_event.next_event:
                    self.current_event = self.current_event.next_event
                    self.current_event.start()
                else:
                    self.finished = True
                    self.running = False
                    continue

            self.current_event.update()

            await asyncio.sleep(1/self.fps)

        return False

class WaitEvent(Event):
    """ Will wait for a certain amount of time and then give way to the next event """
    delay_ms: int = 0

    def __init__(self, delay_ms: int):
        self.delay_ms = int(delay_ms)

    def update(self):
        now = utime.ticks_ms()
        if self.started_ms + self.delay_ms < now:
            self.finished = True
            self.active = False

class OneShotEvent(Event):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def start(self):
        super().start()

        self.active = True
        self.do_thing()
        self.finished = True
        self.active = False

    def do_thing(self):
        """ Override """
        pass

class MultiEvent(Event):
    events = []
    
    """ A class that allows multiple other events to fire off at once"""
    def __init__(self, events):
        self.events = events

    def start(self):
        super().start()
        self.active = True
        for event in self.events:
            event.start()
        self.finished = True
        self.active = False
    
class SpawnEnemyEvent(OneShotEvent):
    dead_pool: None
    active_sprites: None

    x: int
    y: int
    z: int
    lane: int

    def __init__(self, x=0, y=0, z=0, lane=0, dead_pool=None):
        super().__init__()

        self.dead_pool = dead_pool

        self.x = x
        self.y = y
        self.z = z
        self.lane = lane

    def do_thing(self):
        print("-- SPAWN EVENT --")
        sprite = self.dead_pool.get_new()
        if not sprite:
            return False

        sprite.reset()


        sprite.x = self.x
        sprite.y = self.y
        sprite.z = self.z

        sprite.set_lane(self.lane)

        return sprite

class MoveCircle(Event):
    item: None
    center: []
    radius: int = 0
    speed: int = 0
    total_count: int = 3
    curr_count: int = 0
    orig_x: int = 0
    orig_y: int = 0

    def __init__(self, item, center, radius, speed, count):
        self.item = item # Sprite object with X and Y
        self.center = center
        self.radius = radius
        self.speed = speed
        self.count = count
        self.orig_x = item.x
        self.orig_y = item.y

    def update(self):
        # print("move circle")
        elapsed = super().update()
        if not elapsed:
            return False

        age = utime.ticks_ms() - self.started_ms
        distance = (age * self.speed) / 1000
        angle = distance * 2 * math.pi / self.radius

        # self.item.x = self.orig_x + (self.center[0] - self.orig_x) + math.sin(angle) * self.radius
        # self.item.y = self.orig_y + (self.center[1] - self.orig_y) + math.cos(angle) * self.radius

        if distance >= 2 * math.pi * self.curr_count and distance < 2 * math.pi * (self.curr_count + 1):
            self.curr_count += 1

        if self.curr_count >= self.total_count:
            return False






