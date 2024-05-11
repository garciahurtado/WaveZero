from sprites.scaled_sprite import ScaledSprite
from sprites.sprite import Sprite


class RoadBarrier(ScaledSprite):
    def __init__(self, *args, **kwargs):
        super().__init__(
            frame_width=20,
            frame_height=15,
            **kwargs)

        self.pos_type = Sprite.POS_TYPE_FAR


    def reset(self):
        """ initial conditions of the sprite before appearing on screen"""
        super().reset()
        self.has_alpha = False
        self.y = 0
        self.z = 1300
        self.speed = -100
