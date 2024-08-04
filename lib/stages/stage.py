

class Stage:
    def __init__(self, sprite_manager):
        self.sprite_manager = sprite_manager
        self.events = []
        self.current_event = 0

    def add_events(self, events):
        self.events.extend(events)

    def update(self, elapsed):
        if self.current_event < len(self.events):
            event = self.events[self.current_event]
            event.update()
            if isinstance(event, SpawnEvent):
                self.sprite_manager.create(event.sprite_type, lane=event.lane, z=event.z)
            if event.completed:
                self.current_event += 1

    def reset(self):
        self.current_event = 0
        for event in self.events:
            event.reset()