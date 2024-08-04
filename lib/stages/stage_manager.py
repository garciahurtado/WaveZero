# from stage_manager import StageManager, Stage, Event, WaitEvent, SpawnEvent, MultiEvent

class Stage1(Stage):
    def __init__(self, sprite_manager):
        super().__init__(sprite_manager)

        spawn_z = 1500
        wall_wait = 2000

        self.add_events([
            MultiEvent([
                SpawnEvent("barrier", lane=0, z=spawn_z),
                SpawnEvent("barrier", lane=1, z=spawn_z),
                SpawnEvent("barrier", lane=3, z=spawn_z),
                SpawnEvent("barrier", lane=4, z=spawn_z),
                WaitEvent(wall_wait),
            ], times=3),
            WaitEvent(wall_wait),
            MultiEvent([
                SpawnEvent("tri", lane=1, z=spawn_z),
                SpawnEvent("tri", lane=2, z=spawn_z),
                WaitEvent(wall_wait),
            ]),
            # Add more events as needed
        ])

"""
# In your main game loop:
sprite_manager = SpriteManager(display, max_sprites=100, camera=camera, lane_width=lane_width)
stage_manager = StageManager(sprite_manager)

# Add sprite types
sprite_manager.add_type("barrier", "/img/road_barrier_yellow.bmp", speed=100, width=12, height=22, color_depth=8,
                        palette=some_palette)
sprite_manager.add_type("tri", "/img/laser_tri.bmp", speed=150, width=16, height=16, color_depth=8,
                        palette=some_palette)

# Add stages
stage_manager.add_stage(Stage1(sprite_manager))

# Start the first stage
stage_manager.start_stage(0)

# In your game loop
while True:
    elapsed = get_elapsed_time()
    stage_manager.update(elapsed)
    stage_manager.show(display)
    # Other game loop logic...

"""

class Event:
    def __init__(self):
        self.completed = False

    def update(self):
        pass

    def reset(self):
        self.completed = False


class WaitEvent(Event):
    def __init__(self, duration):
        super().__init__()
        self.duration = duration
        self.start_time = None

    def update(self):
        if self.start_time is None:
            self.start_time = utime.ticks_ms()
        elif utime.ticks_diff(utime.ticks_ms(), self.start_time) >= self.duration:
            self.completed = True

    def reset(self):
        super().reset()
        self.start_time = None


class SpawnEvent(Event):
    def __init__(self, sprite_type, lane, z):
        super().__init__()
        self.sprite_type = sprite_type
        self.lane = lane
        self.z = z

    def update(self):
        # The actual spawning will be handled by the Stage class
        self.completed = True


class MultiEvent(Event):
    def __init__(self, events, times=1):
        super().__init__()
        self.events = events
        self.times = times
        self.current_time = 0
        self.current_event = 0

    def update(self):
        if self.current_time < self.times:
            if self.current_event < len(self.events):
                self.events[self.current_event].update()
                if self.events[self.current_event].completed:
                    self.current_event += 1
            else:
                self.current_event = 0
                self.current_time += 1
                for event in self.events:
                    event.reset()
        else:
            self.completed = True

    def reset(self):
        super().reset()
        self.current_time = 0
        self.current_event = 0
        for event in self.events:
            event.reset()

class StageManager:
    def __init__(self, sprite_manager):
        self.sprite_manager = sprite_manager
        self.stages = []
        self.current_stage = None

    def add_stage(self, stage):
        self.stages.append(stage)

    def start_stage(self, index):
        if 0 <= index < len(self.stages):
            self.current_stage = self.stages[index]
            self.current_stage.reset()

    def update(self, elapsed):
        if self.current_stage:
            self.current_stage.update(elapsed)
            self.sprite_manager.update_all(elapsed)

    def show(self, display):
        if self.current_stage:
            self.sprite_manager.show_all(display)
