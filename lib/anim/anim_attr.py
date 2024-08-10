import math

import uasyncio as asyncio
import utime

from anim.animation import Animation


class AnimAttr(Animation):
    start_value: None
    end_value: None
    sign = +1  # Whether to increment (+1) or decrement (-1) the value (this is not the increment step)

    def __init__(self, anim_obj, anim_property, end_value, duration, easing=None):
        super().__init__(anim_obj, anim_property, duration)

        self.end_value = end_value

        if self.start_value < self.end_value:
            self.sign = +1
        else:
            self.sign = -1

        self.easing = easing or self.linear_easing

    @staticmethod
    def linear_easing(t):
        return t

    @staticmethod
    def ease_in_cubic(t):
        return t * t * t

    @staticmethod
    def ease_in_sine(t):
        return 1 - math.cos((t * math.pi) / 2)

    @staticmethod
    def ease_in_out_sine(t):
        return -(math.cos(math.pi * t) - 1) / 2

    async def run_loop(self):
        self.elapsed = utime.ticks_diff(utime.ticks_us(), self.started)

        if self.elapsed == 0:
            step = 0
        else:
            step = min((self.elapsed / 1000) / self.duration, 1)

        # Apply easing function
        eased_step = self.easing(step)

        new_value = self.start_value + (self.end_value - self.start_value) * eased_step

        # Check for stop condition
        if eased_step >= 1:
            setattr(self.anim_obj, self.anim_property, self.end_value)
            self.stop()
        else:
            setattr(self.anim_obj, self.anim_property, int(new_value))


    def stop(self):
        self.running = False

