import utime
from micropython import const

LIST_SIZE = const(20)

class FpsCounter():
    ticks: [int] = [0] * LIST_SIZE
    index: int = 0
    ellapsed: int = 0

    def tick(self):
        """ Get current timestamp at the time of rendering one frame, to calculate FPS later
        """
        self.ticks[self.index] = (utime.ticks_ms()) % (256*256)
        self.index = self.index + 1
        if self.index >= LIST_SIZE:
            self.index = 0
            
    def fps(self):
        """
        Calculate FPS based on the timestamp measurements recorded
        """
        if self.index == 0:
            start = self.index
            end = -1
        else:
            start = self.index
            end = self.index - 1
            
        if self.ticks[start] == 0 or self.ticks[end] == 0:
            return 0

        self.ellapsed = self.ticks[end] - self.ticks[start]
        avg_ms = self.ellapsed / len(self.ticks)
        
        if avg_ms == 0:
           return 0
           
        return 1000 / avg_ms
        

        