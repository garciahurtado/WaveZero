from sprites.scaled_sprite import ScaledSprite
from sprites.sprite import Sprite
from stages.events import EventChain, WaitEvent, MoveCircle

class FlyingTri(ScaledSprite):
    def __init__(self, *args, **kwargs):
        super().__init__(
            z=200,
            frame_width=20,
            frame_height=20,
            **kwargs)

        self.pos_type = Sprite.POS_TYPE_NEAR
        self.init_behavior()


    def reset(self):
        """ initial conditions of the sprite before appearing on screen"""
        super().reset()
        self.set_alpha(0)
        self.y = 45
        self.z = -50
        self.speed = 6

    def init_behavior(self):
        chain = EventChain()

        all_events = [
            WaitEvent(5000),
            MoveCircle(self, {'x': 0, 'y': 100}, 40, 200, 5)
        ]

        chain.add_many(all_events)

        self.event_chain = chain

