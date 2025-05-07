from sprites.sprite_types import *

class WarningWall(SpriteType):
    name = SPRITE_BARRIER_LEFT
    # image_path = "/img/road_barrier_yellow.bmp"
    image_path = "/img/road_barrier_yellow_32.bmp"
    # width = 24
    # height = 15
    width = 32
    height = 32
    color_depth = 4
    alpha_color = 0x0
    num_frames = 24

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
