import asyncio
from rotary_irq import RotaryIRQ


class InputHandler:
    def __init__(self, bike):
        self.bike = bike
        self.init_input()

    def init_input(self):
        self.encoder = RotaryIRQ(
            26,
            27,
            half_step=False,
            incr=1
        )
        print("Created input handler")

    def add_listener(self, listener, my_self=None):
        if my_self:
            self.encoder.add_listener([listener, my_self])
        else:
            self.encoder.add_listener(listener)

    async def get_input(self, encoder, last_pos):
        fps = 60
        while True:
            if self.bike.moving == True:
                """ Supress input when the bike is already moving """
                await asyncio.sleep(1 / fps)
                continue

            # position = encoder.value()
            # if position == last_pos['pos']:
            #     pass
            # elif position > last_pos['pos']:
            #     last_pos['pos'] = position
            #     self.bike.move_left()
            # elif position < last_pos['pos']:
            #     last_pos['pos'] = position
            #     self.bike.move_right()

            await asyncio.sleep(1 / fps)


    def read_input(self, value):
        print(f"Rotary value {value}")


def make_input_handler(bike):
    input_handler = InputHandler(bike)
    input_handler.add_listener(input_handler.read_input, input_handler)
    return input_handler