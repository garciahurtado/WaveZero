from sprites2.sprite_types import SpriteType
from sprites2.sprite_types import *

class WarningWall(SpriteType):
    name = SPRITE_BARRIER_LEFT
    image_path = "/img/road_barrier_yellow.bmp"
    speed = -50
    width = 24
    height = 15
    color_depth = 4
    alpha = None

    repeats = 2
    repeat_spacing = 24

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
