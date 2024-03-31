import ulab.numpy as np
import time

class FpsCounter():
    def __init__(self, list_size=20):
        self.list_size = list_size
        self.ticks = np.zeros(list_size, dtype=np.uint16)
        self.index = 0
        
    def tick(self):
        """ Get current timestamp at the time of rendering one frame, to calculate FPS later
        """
        self.ticks[self.index] = (time.monotonic() * 1000) % (256*256)
        self.index = self.index + 1
        if self.index >= len(self.ticks):
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
        
        ellapsed = self.ticks[end] - self.ticks[start]
        avg_ms = ellapsed / len(self.ticks)
        
        if avg_ms == 0:
           return 0
           
        fps = 1000 / avg_ms
        
        return fps
        
            
        