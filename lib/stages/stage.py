import asyncio

from stages.events import MultiEvent, WaitEvent, SpawnEnemyEvent, EventChain, SequenceEvent


class Stage:
    """
    A stage is mainly a series of events which are chained to one another so that they will be executed in
    sequence. These events can be multiple in parallel, wait events or enemy spawn events.
    Meant to be subclassed by individual stages
    """
    events = EventChain()
    running = False

    def __init__(self, sprite_manager):
        self.sprite_manager = sprite_manager
        self.current_event = 0

    def start(self):
        # self.reset()
        self.running = True
        self.events.start()
        # self.current_event

    def stop(self):
        self.running = False

    def add_events(self, events):
        for event in events:
            self.events.add(event)

    def queue(self, event=None):
        if isinstance(event, list):
            return self.add_events(event)
        elif event:
            self.events.add(event)
        else:
            return self

    def update(self, elapsed):
        """ Update the current event in the stage, provided it is running"""
        if not self.running:
            return False

        loop = asyncio.get_event_loop()
        loop.create_task(self.events.update())


    def reset(self):
        self.current_event = 0
        self.events.reset()

    """ Event aliases.
     These work differently than the ones in EvenChain, in that these return the Event object, so no fluent interface
     is possible """

    def multi(self, events, repeat=1):
        """MultiEvent Factory"""
        next_event = MultiEvent(events, repeat=repeat)
        self.events.add(next_event)
        return self

    def sequence(self, events, repeat=1):
        """SequenceEvent Factory"""
        next_event = SequenceEvent(events, repeat=repeat)
        self.events.add(next_event)
        return self

    def wait(self, delay_ms):
        """WaitEvent Factory"""
        next_event = WaitEvent(delay_ms)
        self.events.add(next_event)
        return self

    def spawn(self, sprite_type, x=0, y=0, z=0, lane=0):
        """SpawnEvent Factory"""
        next_event = SpawnEnemyEvent(sprite_type, x=x, y=y, z=z, lane=lane, sprite_mgr=self.sprite_manager)
        self.events.add(next_event)
        return self

