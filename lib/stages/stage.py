from stages.events import MultiEvent, WaitEvent, SpawnEnemyEvent, EventChain
class Stage:
    """ A stage is mainly a series of events which are chained to one another so that they will be executed in
    sequence. These events can be multiple in parallel, wait events or enemy spawn events."""
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
        # if not self.running:
        #     return False

        self.events.update()

        # if self.current_event < len(self.events):
        #     # print(f"UPDATE {self.current_event} len:{len(self.events)}")
        #
        #     event = self.events[self.current_event]
        #     if event.active:
        #         if not event.update():
        #             self.current_event += 1
        #             self.events[self.current_event].start()

    def reset(self):
        self.current_event = 0
        self.events.reset()

    """ Event aliases """

    def multi(self, *events, repeat=1):
        """MultiEvent Factory"""
        self.queue(MultiEvent(*events, repeat=repeat))
        return self

    def wait(self, delay_ms):
        """WaitEvent Factory"""
        self.queue(WaitEvent(delay_ms))
        return self

    def spawn(self, sprite_type, x=0, y=0, z=0, lane=0):
        """SpawnEvent Factory"""
        self.queue(SpawnEnemyEvent(sprite_type, x=x, y=y, z=z, lane=lane, sprite_mgr=self.sprite_manager))
        return self
