import asyncio

import utime


class Animation:
    """A base animation class used to animate properties of objects over time. It supports both endless and timed
    animations, but the details are left to the subclasses """

    duration: int
    elapsed: int
    started_ms: int
    anim_obj: None
    anim_property: None
    running = False

    def __init__(self, anim_obj, anim_property, duration=0):
        self.anim_obj = anim_obj
        self.anim_property = anim_property
        if anim_property:
            self.start_value = getattr(anim_obj, anim_property)
        self.duration = duration
        self.elapsed = 0
        self.running = False

    async def run(self, fps=60):
        self.running = True
        self.started = utime.ticks_us()

        while self.running:
            await self.run_loop()
            await asyncio.sleep(1 / fps)

        return True

    async def run_loop(self):
        """ Must be implemented in child classes"""
        pass

    def stop(self):
        self.running = False

