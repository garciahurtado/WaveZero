from rotary_irq import RotaryIRQ
from micropython import const

class InputHandler:
    LEFT = const(0)
    RIGHT = const(1)
    ACTION = const(2)

    def __init__(self, player):
        self.player = player
        self.last_pos = 0
        self.init_input()

    def init_input(self):
        self.encoder = RotaryIRQ(
            26,
            27,
            half_step=False,
            incr=1
        )
        print("--- Created input handler ---")

    def read_input(self, position):
        if self.player.moving:
            """Suppress input when the player is already moving"""
            return

        position = int(self.encoder.value())

        if position != self.last_pos:
            if position > self.last_pos:
                self.player.move_right()
            elif position < self.last_pos:
                self.player.move_left()
            self.last_pos = position
    def add_listener(self, listener, my_self=None):
        if my_self:
            self.encoder.add_listener((listener, my_self))
        else:
            self.encoder.add_listener(listener)


def make_input_handler(bike):
    input_handler = InputHandler(bike)
    input_handler.add_listener("read_input", input_handler)
    return input_handler