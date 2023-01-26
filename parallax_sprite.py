from displayio import Group
from adafruit_display_shapes.rect import Rect
import time
import math

SCREEN_WIDTH = 96
SCREEN_HEIGHT = 64

class ParallaxSprite():
    
    def __init__(self, sprite, x=0, y=0, start_y=0):
        now = time.monotonic() * 1000
        self.last_update = now
        self.speed = 10
        self.fine_y = sprite.y
        self.sprite = sprite
        self.width = sprite.width
        self.height = sprite.height
        self.start_y = start_y
        
         
    def update(self):
        rel_speed = abs(math.sin( (self.fine_y - self.start_y)   / (SCREEN_HEIGHT - self.start_y ))  + 0.01)
        self.fine_y += rel_speed * self.speed
        width = round(rel_speed * self.speed)
        self.sprite = Rect(x=self.sprite.x, y=round(self.fine_y), width=width, height=width*2, fill=0x000066, outline=0x33AAFF)
        self.sprite.y = round(self.fine_y)
        
        