import asyncio

import utime


class Animation:
    duration_ms: int
    ellapsed_ms: int
    started_ms: int
    anim_obj: None
    anim_property: None
    start_value: None
    end_value: None
    running = False
    incr = +1 # Whether to increment (+1) or decrement (-1) the value

    def __init__(self, anim_obj, anim_property, end_value, duration):
        self.anim_obj = anim_obj
        self.anim_property = anim_property
        self.start_value = getattr(anim_obj, anim_property)
        self.end_value = end_value
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

        while self.running:
            self.ellapsed_ms = utime.ticks_diff(utime.ticks_ms(), self.started_ms)

            if self.ellapsed_ms == 0:
                ratio = 0
            else:
                ratio = self.ellapsed_ms / self.duration_ms

            new_value = self.start_value + (self.end_value - self.start_value) * ratio
            new_value = int(new_value)

            if (
                    ((self.incr == -1) and (new_value <= self.end_value)) or
                    ((self.incr == +1) and (new_value >= self.end_value))
                ):
                setattr(self.anim_obj, self.anim_property, self.end_value)
                self.stop()

            setattr(self.anim_obj, self.anim_property, new_value)

            await asyncio.sleep(1 / fps)

        return True


    def stop(self):
        self.running = False

