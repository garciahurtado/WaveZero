from sprites.sprite_types import SpriteType, SPRITE_LASER_TRI


class LaserTri(SpriteType):
    name = SPRITE_LASER_TRI
    image_path = "/img/laser_tri.bmp"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
