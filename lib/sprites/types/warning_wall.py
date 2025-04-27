from sprites.sprite_types import *

class WarningWall(SpriteType):
    name = SPRITE_BARRIER_LEFT
    image_path = "/img/road_barrier_yellow.bmp"
    width = 24
    height = 15
    color_depth = 4
    alpha_color = None
    num_frames = 1

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
