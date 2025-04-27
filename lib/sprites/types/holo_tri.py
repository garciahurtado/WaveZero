from sprites.sprite_types import *

class HoloTri(SpriteType):
    name = SPRITE_HOLO_TRI
    image_path = "/img/holo_tri.bmp"
    speed = -150
    width = 20
    height = 20
    color_depth = 4
    alpha = None

    def __init__(self):
        super().__init__()

        self.name = SPRITE_HOLO_TRI
        self.image_path = "/img/holo_tri.bmp"
        self.speed = 200
        self.width = 24
        self.height = 15
        self.color_depth = 4
        self.alpha = None
        self.repeats = 4,
        self.repeat_spacing = 26
