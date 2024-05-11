import utime
from micropython import const

LIST_SIZE = const(40)

class FpsCounter():
    ticks: [int] = [0] * LIST_SIZE
    index: int = 0
    ellapsed = 0

    def tick(self):
        """ Get current timestamp at the time of rendering one frame, to calculate FPS later
        """
        self.ticks[self.index] = utime.ticks_ms()
        self.index = self.index + 1
        if self.index >= LIST_SIZE:
            self.index = 0

        return self.ticks[self.index]

    def fps(self):
        """
        Calculate FPS based on the timestamp measurements recorded
        """
        start = self.index

        if self.index == 0:
            end = -1
        else:
            end = self.index - 1

        if self.ticks[start] == 0 or self.ticks[end] == 0:
            return 0

        self.ellapsed = self.ticks[end] - self.ticks[start]
        if self.ellapsed <= 0 or len(self.ticks) == 0:
            return False

        avg_ms = self.ellapsed // len(self.ticks)
        
        if avg_ms <= 0:
           return False
           
        return 1000 / avg_ms
