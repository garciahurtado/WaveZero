import uasyncio as asyncio
import math

import utime
class Event:
    started_ms: int
    active: bool = False
    finished: bool = False
    next_event = None
    speed: int = 0
    elapsed = 0
    last_tick = 0

    def start(self):
        self.started_ms = utime.ticks_ms()
        self.active = True
        self.finished = False

    def update(self):
        """ Override and call from child classes """
        if not self.active:
            return False

        if not self.last_tick:
            self.last_tick = self.started_ms

        # elapsed = utime.ticks_ms() - self.last_tick
        return True

    def finish(self):
        self.finished = True
        self.active = False
        return self.on_finish()

    def reset(self):
        self.finished = True
        self.active = False

    def on_finish(self):
        """on_finish handler should be overridden in children classes"""
        if self.next_event:
            self.next_event.start()
        pass


class EventChain(Event):
    """ A list of events that will be executed from first to last"""
    events: [] = []
    current_event: Event = None
    finished: bool = False

    def start(self):
        super().start()
        self.current_event = self.events[0]
        print(self.current_event)
        self.current_event.start()

    def reset(self):
        self.active = False
        self.current_event = self.events[0]
        # TODO: add task cancellation

    def add(self, new_event: Event):
        """ Chain it to the last event added before this one"""
        if len(self.events) > 0:
            last: Event = self.events[-1]
            last.next_event = new_event

        self.events.append(new_event)

    def add_many(self, all_events):
        for event in all_events:
            self.add(event)

    def update(self):
        if not super().update():
            return False

        if self.current_event.finished:
            if self.current_event.next_event:
                next_event = self.current_event.next_event
                self.current_event = next_event
                self.current_event.start()
            else:
                self.finish()

        self.current_event.update()

        return True

class WaitEvent(Event):
    """ Will wait for a certain amount of time and then give way to the next event """
    delay_ms: int = 0

    def __init__(self, delay_ms: int):
        self.delay_ms = int(delay_ms)

    def start(self):
        self.started_ms = utime.ticks_ms()
        self.active = True
        self.finished = False

    def update(self):
        if not super().update():
            return False

        now = utime.ticks_ms()
        if utime.ticks_diff(now, self.started_ms) > self.delay_ms:
            self.finish()
            return False


class MultiEvent(Event):
    events = []
    repeat_max = 0
    repeat_count = 0

    """ A class that allows multiple other events to fire off at once
        `times` allows us to repeat the whole set of events more than once 
        (once the first set is finished)
    """
    def __init__(self, *events, repeat=1):
        self.events = events
        self.repeat_max = repeat

    def start(self):
        super().start()

        self.active = True
        self.finished = False

        for event in self.events:
            event.start()
            
    def finish(self):
        super().finish()


    def update(self):
        if not super().update():
            return False

        for event in self.events:
            if event.finished:
                continue
            else:
                event.update()
                return True

        """All events finished"""
        self.repeat_count += 1

        for reset_event in self.events:
            reset_event.reset()

        if (self.repeat_count >= self.repeat_max):
            self.finish()
            return False
        else:
            self.start()


class OneShotEvent(Event):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def start(self):
        super().start()
        self.do_thing()
        self.finish()

    def do_thing(self):
        """ Override """
        pass


class SpawnEnemyEvent(OneShotEvent):
    sprite_mgr: None

    x: int
    y: int
    z: int
    lane: int

    def __init__(self, sprite_type, x=0, y=0, z=0, lane=0, sprite_mgr=None):
        super().__init__()

        self.sprite_mgr = sprite_mgr

        self.x = x
        self.y = y
        self.z = z
        self.sprite_type = sprite_type
        self.lane = lane

    def do_thing(self):
        sprite, _ = self.sprite_mgr.create(self.sprite_type, x=self.x, y=self.y, z=self.z)
        self.sprite_mgr.set_lane(sprite, self.lane)
        self.finish()

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






