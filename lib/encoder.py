# Class to monitor a rotary encoder and update a value.  You can either read the value when you need it, by calling getValue(), or
# you can configure a callback which will be called whenever the value changes.
from machine import Pin

class Encoder:
    def __init__(self, left_pin, right_pin, callback=None):
        self.left_pin = left_pin
        self.right_pin = right_pin
        self.value = 0
        self.state = '00'
        self.direction = None
        self.callback = callback

        self.left_pin = Pin(self.left_pin, Pin.IN, Pin.PULL_DOWN)
        self.right_pin = Pin(self.right_pin, Pin.IN, Pin.PULL_DOWN)

        self.left_pin.irq(trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING, handler=self.transition_occurred)
        self.right_pin.irq(trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING, handler=self.transition_occurred)

    def transition_occurred(self, pin):
        new_state = "{}{}".format(self.left_pin.value(), self.right_pin.value())

        if self.state == "00":  # Resting position
            if new_state == "01":  # Turned right 1
                self.direction = "R"
            elif new_state == "10":  # Turned left 1
                self.direction = "L"

        elif self.state == "01":  # R1 or L3 position
            if new_state == "11":  # Turned right 1
                self.direction = "R"
            elif new_state == "00":  # Turned left 1
                if self.direction == "L":
                    self.value = self.value - 1
                    if self.callback is not None:
                        self.callback(self.value, self.direction)

        elif self.state == "10":  # R3 or L1
            if new_state == "11":  # Turned left 1
                self.direction = "L"
            elif new_state == "00":  # Turned right 1
                if self.direction == "R":
                    self.value = self.value + 1
                    if self.callback is not None:
                        self.callback(self.value, self.direction)

        else:  # self.state == "11"
            if new_state == "01":  # Turned left 1
                self.direction = "L"
            elif new_state == "10":  # Turned right 1
                self.direction = "R"
            elif new_state == "00":  # Skipped an intermediate 01 or 10 state, but if we know direction then a turn is complete
                if self.direction == "L":
                    self.value = self.value - 1
                    if self.callback is not None:
                        self.callback(self.value, self.direction)
                elif self.direction == "R":
                    self.value = self.value + 1
                    if self.callback is not None:
                        self.callback(self.value, self.direction)

        self.state = new_state

    def get_value(self):
        return self.value