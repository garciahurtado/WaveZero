import asyncio

import time

from profiler import Profiler as prof
from anim.animation import Animation

class PaletteRotateOne(Animation):
    color_idx = 0
    current_idx = 0
    elapsed_ms = 0
    last_change_ms = 0
    running = False

    def __init__(self, orig_palette, color_list, interval_ms, idx=1):
        """ Default to idx=1 because 0 is the color index that is usually transparent """

        super().__init__(orig_palette, None)
        self.orig_palette = orig_palette
        self.color_list = color_list
        self.interval_ms = interval_ms
        self.last_change_ms = time.ticks_ms()
        self.idx = idx # Color index in the original palette that we will rotate

    async def run_loop(self):
        now = time.ticks_ms()
        delta = time.ticks_diff(now, self.last_change_ms)
        color_list = self.color_list

        if delta > self.interval_ms:
            self.current_idx = (self.current_idx + 1) % len(color_list)
            new_color = color_list.get_int(self.current_idx)


            self.orig_palette.set_int(self.idx, new_color)
            self.last_change_ms = time.ticks_ms()


        await asyncio.sleep_ms(self.interval_ms)
