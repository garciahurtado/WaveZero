from machine import Pin
import utime

single = None

class StatusLEDs:
    def __init__(self):
        self.pin_led1 = Pin(10, Pin.OUT, value=0)
        self.pin_led2 = Pin(11, Pin.OUT, value=0)
        self.pin_led3 = Pin(12, Pin.OUT, value=0)
        self.pin_led4 = Pin(13, Pin.OUT, value=0)

        """ index by Pin order"""
        self.leds = [0, self.pin_led1, self.pin_led2, self.pin_led3, self.pin_led4]

    def blink_led(self, num):
        my_led = self.leds[num]
        my_led.value(1)
        utime.sleep_ms(20)
        my_led.value(0)

def get_status_led_obj():
    global single
    if not single:
        single = StatusLEDs()

    return single