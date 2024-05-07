import asyncio
import utime
class Event:
    started_ms: int
    active: bool = False
    finished: bool = False
    next_event = False

    def start(self):
        self.started_ms = utime.ticks_ms()
        self.active: True

    def update(self):
        """ Override in child classes """
        if self.active:
            return True
        else:
            return False

class EventChain:
    events: [] = []
    current_event: Event = None
    finished: bool = False
    running: bool = False

    def start(self):
        self.running = True
        self.current_event = self.events[0]
        print(self.current_event)
        self.current_event.start()

        loop = asyncio.get_event_loop()
        loop.create_task(self.update())

    def add(self, new_event: Event):
        """ Chain it to the last event"""
        if len(self.events) > 0:
            last: Event = self.events[-1]
            last.next_event = new_event

        self.events.append(new_event)

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

            await asyncio.sleep(1/30)

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
    def start(self):
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
    res_pool: None
    active_pool: None
    enemy_pool: None

    x: int
    y: int
    z: int
    speed: int
    lane: int

    def __init__(self, res_pool, active_pool, x: int=0, y: int=0, z: int=0, speed: int=0, lane: int=0, enemy_pool=None):
        self.res_pool = res_pool
        self.active_pool = active_pool
        self.enemy_pool = enemy_pool

        self.x = x
        self.y = y
        self.z = z
        self.speed = speed
        self.lane = lane

    def do_thing(self):
        sprite = self.res_pool.get_new()
        sprite.x = self.x
        sprite.y = self.y
        sprite.z = self.z
        sprite.speed = self.speed
        sprite.set_lane(self.lane)
        self.active_pool.append(sprite)
        self.enemy_pool.append(sprite)

        return sprite


