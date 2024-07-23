from sprites.scaled_sprite import ScaledSprite
from sprites.sprite import Sprite


class RoadBarrier(ScaledSprite):
    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            frame_width=20,
            frame_height=15,
            **kwargs)

        self.pos_type = Sprite.POS_TYPE_FAR


    def reset(self):
        """ initial conditions of the sprite before appearing on screen"""
        super().reset()
        self.has_alpha = False
        self.speed = -0.1
