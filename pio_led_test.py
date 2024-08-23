from machine import Pin
from rp2 import PIO, StateMachine, asm_pio
import utime

LED_PIN = 18  # Onboard LED pin for Raspberry Pi Pico

@asm_pio(set_init=PIO.OUT_LOW)
def blink():
    wrap_target()
    set(pins, 1)   [31]  # Turn LED on and delay
    nop()          [31]  # Additional delay
    set(pins, 0)   [31]  # Turn LED off and delay
    nop()          [31]  # Additional delay
    wrap()

class PIOLEDController:
    def __init__(self):
        self.sm = StateMachine(0, blink, freq=2000, set_base=Pin(LED_PIN))
        print(f"PIO initialized with LED on pin {LED_PIN}")

    def start_blink(self):
        print("Starting LED blink")
        self.sm.active(1)

    def stop_blink(self):
        print("Stopping LED blink")
        self.sm.active(0)

    def manual_toggle(self, count=5, delay_ms=500):
        led = Pin(LED_PIN, Pin.OUT)
        for _ in range(count):
            print("LED ON")
            led.value(1)
            utime.sleep_ms(delay_ms)
            print("LED OFF")
            led.value(0)
            utime.sleep_ms(delay_ms)

# Usage
controller = PIOLEDController()

print("Testing PIO blink")
controller.start_blink()
utime.sleep(5)  # Let it blink for 5 seconds
controller.stop_blink()

print("Testing manual toggle")
controller.manual_toggle()

print("Test complete")