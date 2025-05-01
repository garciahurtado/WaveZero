import uasyncio as asyncio
import math

import utime

from mpdb.mpdb import Mpdb
from profiler import Profiler as prof
from sprites.sprite_manager import SpriteManager

class Event:
    started_ms: int
    active: bool = False
    finished: bool = False
    next_event = None
    speed: int = 0
    elapsed = 0
    last_tick = 0
    sprite_manager = None
    extra_kwargs = None

    def __init__(self, **kwargs):
        self.extra_kwargs = kwargs

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

    def reset(self):
        self.finished = True
        self.active = False

    """ Event aliases / Static methods """

    @staticmethod
    def multi(events, repeat=1):
        """MultiEvent Factory"""
        this_event = MultiEvent(events, repeat=repeat)
        return this_event

    @staticmethod
    def sequence(events, repeat=1):
        """SequenceEvent Factory"""
        this_event = SequenceEvent(events, repeat=repeat)
        return this_event

    @staticmethod
    def wait(delay_ms):
        """WaitEvent Factory"""
        this_event = WaitEvent(delay_ms)
        return this_event

    @staticmethod
    def spawn(sprite_type, x=0, y=0, z=0, lane=0, **kwargs):

        """SpawnEvent Factory"""
        all_kwargs = {
            'x': x,
            'y': y,
            'z': z,
            'lane': lane
        }

        all_kwargs = all_kwargs | kwargs

        # all_kwargs has all the entity properties that need to be set upon spawn
        this_event = SpawnEnemyEvent(sprite_type, sprite_mgr=Event.sprite_manager, **all_kwargs)
        return this_event


class EventChain(Event):
    """ A list of events that will be executed from first to last"""
    events: [] = []
    current_event: Event = None
    finished: bool = False
    sprite_manager: SpriteManager = None

    def start(self, sprite_manager=None):
        self.sprite_manager = sprite_manager

        super().start()
        self.current_event = self.events[0]
        self.current_event.start()

    def reset(self):
        self.active = False
        self.current_event = self.events[0]
        # TODO: add task cancellation

    def add(self, new_event: Event):
        """ Chain the last event added to this one"""
        if len(self.events) > 0:
            last: Event = self.events[-1]
            last.next_event = new_event

        self.events.append(new_event)

    def add_many(self, all_events):
        for event in all_events:
            self.add_sprite(event)

    async def update(self):
        if not super().update():
            await asyncio.sleep_ms(10)
            return False

        if self.current_event.finished:
            if self.current_event.next_event:
                next_event = self.current_event.next_event
                self.current_event = next_event
                self.current_event.start()
            else:
                """ No more events """
                self.finish()
        else:
            await asyncio.sleep_ms(10)
            return self.current_event.update()

        await asyncio.sleep_ms(10)
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

    def __init__(self, events, repeat=1):
        self.events = events
        self.repeat_max = repeat

    def start(self):
        super().start()

        self.active = True
        self.finished = False

        for event in self.events:
            event.start()

    def update(self):
        if not super().update():
            return False
        all_finished = True
        for event in self.events:
            if event.finished or not event.active:
                continue
            else:
                all_finished = False
                event.update()

        if not all_finished:
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


class SequenceEvent(Event):
    events = []
    repeat_max = 0
    repeat_count = 0
    current_event_index = 0

    """ A class that allows multiple events to fire off sequentially
        `repeat` allows us to repeat the whole sequence of events more than once 
        (once the first sequence is finished)
    """

    def __init__(self, events, repeat=1):
        self.events = events
        self.repeat_max = repeat

    def start(self):
        super().start()

        self.active = True
        self.finished = False
        self.current_event_index = 0

        if self.events:
            self.events[0].start()

    def update(self):
        if not super().update():
            return False

        if self.current_event_index >= len(self.events):
            self.repeat_count += 1
            if self.repeat_count >= self.repeat_max:
                self.finish()
                return False
            else:
                self.reset()
                self.start()
                return True

        current_event = self.events[self.current_event_index]

        if current_event.finished or not current_event.active:
            self.current_event_index += 1
            if self.current_event_index < len(self.events):
                self.events[self.current_event_index].start()
        else:
            current_event.update()

        return True

    def reset(self):
        super().reset()
        self.current_event_index = 0
        for event in self.events:
            event.reset()


def sequence(self, events, repeat=1):
    """SequenceEvent Factory"""
    next_event = SequenceEvent(events, repeat=repeat)
    self.events.add(next_event)
    return self


class OneShotEvent(Event):
    def start(self):
        super().start()
        self.do_thing()
        self.finish()

    def do_thing(self):
        """ Override """
        raise NotImplementedError("You must implement event.do_thing()")


class SpawnEnemyEvent(OneShotEvent):
    sprite_mgr: None

    x: int
    y: int
    z: int
    lane: int

    def __init__(self, sprite_type, x=0, y=0, z=0, lane=0, sprite_mgr=None, **kwargs):
        super().__init__(**kwargs)

        self.sprite_mgr = sprite_mgr

        self.x = x
        self.y = y
        self.z = z
        self.sprite_type = sprite_type
        self.lane = lane

    def do_thing(self):
        sprite_type = self.sprite_type

        base_args = {
            'x': self.x, 'y': self.y, 'z': self.z
        }
        if self.extra_kwargs:
            all_args = base_args | self.extra_kwargs
            sprite, _ = self.sprite_mgr.spawn(sprite_type, **all_args)
        else:
            sprite, _ = self.sprite_mgr.spawn(sprite_type, base_args)

        self.sprite_mgr.set_lane(sprite,
                                 self.lane)  # ??? really?? the SpriteManager should do this within its own lifecycle,
        # or lane should be passed as another extra kwarg from parent spawn()
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
        self.item = item  # Sprite object with X and Y
        self.center = center
        self.radius = radius
        self.speed = speed
        self.count = count
        self.orig_x = item.x
        self.orig_y = item.y

    def update(self):
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
