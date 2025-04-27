from sprites.sprite_types import SpriteType, SPRITE_LASER_ORB


class LaserOrb(SpriteType):
    name = SPRITE_LASER_ORB
    image_path = "/img/laser_orb_grey.bmp"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
