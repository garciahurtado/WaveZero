from sprites2.sprite_types import SpriteType
from sprites2.sprite_types import *

class WarningWall(SpriteType):
    name = SPRITE_BARRIER_LEFT
    image_path = "/img/road_barrier_yellow.bmp"
    speed = -150
    width = 24
    height = 15
    color_depth = 4
    alpha = None
    repeats = 4
    repeat_spacing = 26

    def __init__(self):
        super().__init__()

        self.name = SPRITE_BARRIER_LEFT
        self.image_path = "/img/road_barrier_yellow.bmp"
        self.speed = 200
        self.width = 24
        self.height = 15
        self.color_depth = 4
        self.alpha = None
        self.repeats = 4,
        self.repeat_spacing = 26
