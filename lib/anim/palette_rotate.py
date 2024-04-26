import asyncio

from anim.animation import Animation
from color_util import colors

class PaletteRotate(Animation):
    rotate_values: []

    def __init__(self, anim_obj, duration, interval, rotate_values, color_idx=0):
        super().__init__(anim_obj, None)

        self.anim_obj = anim_obj # Must be an object of type Framebuffer / FramebufferPalette
        self.duration_ms = duration
        self.interval_ms = interval
        self.rotate_values = rotate_values
        self.color_idx = color_idx
        self.current_index = 0
        self.ellapsed_ms = 0
        self.running = False

    async def run_loop(self):
        new_color = self.rotate_values[self.current_index]
        self.anim_obj.pixel(self.color_idx, 0, new_color)

        self.current_index += 1
        if self.current_index >= len(self.rotate_values):
            self.current_index = 0

        await asyncio.sleep(self.interval_ms/1000)