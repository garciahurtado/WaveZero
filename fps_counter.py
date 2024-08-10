import utime as time
from micropython import const

LIST_SIZE = const(40)

class FpsCounter():
    ticks: [int] = [0] * LIST_SIZE
    index: int = 0
    elapsed = 0

    def tick(self):
        """ Get current timestamp at the time of rendering one frame, to calculate FPS later
        """
        self.ticks[self.index] = time.ticks_ms()
        self.index = self.index + 1
        if self.index >= LIST_SIZE:
            self.index = 0

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


        # self.elapsed = self.ticks[end] - self.ticks[start]
        self.elapsed = time.ticks_diff(self.ticks[end], self.ticks[start])

        if self.elapsed <= 0:
            return 0

        if end > start:
            steps = end - start
        else:
            steps = LIST_SIZE - (start - end)

        avg_ms = self.elapsed / steps

        if avg_ms <= 0:
           return 0

        return 1000 / avg_ms
