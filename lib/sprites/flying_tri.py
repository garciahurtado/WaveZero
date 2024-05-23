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
        # self.init_behavior()


    def reset(self):
        """ initial conditions of the sprite before appearing on screen"""
        print("Flying tri reset")
        super().reset()
        self.visible = True
        self.active = True
        self.set_alpha(0)
        self.y = 0
        self.z = -30
        self.speed = 6
        
    def update(self, elapsed):
        print(f"Elapsed: {elapsed} / xyz: {self.x} {self.y} {self.z} ")
        super().update(elapsed)

    def init_behavior(self):
        chain = EventChain()

        all_events = [
            # WaitEvent(5000),
            # MoveCircle(self, {'x': 0, 'y': 100}, 40, 200, 5)
        ]

        chain.add_many(all_events)

        self.event_chain = chain

