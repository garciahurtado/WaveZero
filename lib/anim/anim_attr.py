import asyncio
import utime

from anim.animation import Animation


class AnimAttr(Animation):
    start_value: None
    end_value: None
    incr = +1  # Whether to increment (+1) or decrement (-1) the value (this is not the increment step)

    def __init__(self, anim_obj, anim_property, end_value, duration):
        super().__init__(anim_obj, anim_property, duration)
        self.end_value = end_value

        if self.start_value < self.end_value:
            self.incr = +1
        else:
            self.incr = -1

    async def run_loop(self):
        self.ellapsed_ms = utime.ticks_diff(utime.ticks_ms(), self.started_ms)

        if self.ellapsed_ms == 0:
            step = 0
        else:
            step = self.ellapsed_ms / self.duration_ms

        new_value = self.start_value + (self.end_value - self.start_value) * step
        new_value = int(new_value)

        # Check for stop condition
        if (
                ((self.incr == -1) and (new_value <= self.end_value)) or
                ((self.incr == +1) and (new_value >= self.end_value))
        ):
            setattr(self.anim_obj, self.anim_property, self.end_value)
            self.stop()

        setattr(self.anim_obj, self.anim_property, new_value)


    def stop(self):
        self.running = False

