from animation import Animation
import utime

class PropertyRotate(Animation):
    rotate_values: []

    def __init__(self, anim_obj, anim_property, duration, rotate_values):
        super().__init__(anim_obj, anim_property)

        self.anim_obj = anim_obj
        self.anim_property = anim_property
        self.start_value = getattr(anim_obj, anim_property)
        self.duration_ms = duration
        self.ellapsed_ms = 0
        self.running = False

        if self.start_value < self.end_value:
            self.incr = +1
        else:
            self.incr = -1

    async def run(self, fps=30):
        self.running = True
        self.started_ms = utime.ticks_ms()