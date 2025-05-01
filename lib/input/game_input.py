from input.rotary_irq import RotaryIRQ
from micropython import const

class GameInput:
    """
    Can handle any random combination of inputs and handlers, besides game related ones
    """
    LEFT = const(0)
    RIGHT = const(1)
    ACTION = const(2)
    handler_left = None
    handler_right = None

    pin_dt   = 26
    pin_clk  = 27

    def __init__(self, half_step=False):
        self.last_pos = 0
        self.init_input(half_step)

    def init_input(self, half_step):
        self.encoder = RotaryIRQ(
            self.pin_clk,
            self.pin_dt,
            half_step=half_step,
            incr=1
        )
        self.encoder.add_listener(("read_input", self))

    def read_input(self, position):
        """ This is the direct listener of the IRQ callback from the encoder, which triggers the secondary callback functions """
        position = int(self.encoder.value())

        if position != self.last_pos:
            if position < self.last_pos:
                if self.handler_right:
                    self.handler_right()
            elif position > self.last_pos:
                if self.handler_left:
                    self.handler_left()

            self.last_pos = position

    def add_listener_right(self, listener):
        self.handler_right = listener

    def add_listener_left(self, listener):
        self.handler_left = listener

def make_input_handler(bike):
    input_handler = GameInput(half_step=True)
    input_handler.add_listener_right(bike.move_right)
    input_handler.add_listener_left(bike.move_left)

    return input_handler
