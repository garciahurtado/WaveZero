from sprites.sprite_types import *

class AlienFighter(SpriteType):
    name = SPRITE_ALIEN_FIGHTER
    image_path = "/img/alien_fighter.bmp"
    y = 42
    width = 24
    height = 16
    color_depth = 4
    alpha = None
    speed = -30

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
