from machine import Pin
from rp2 import PIO, StateMachine, asm_pio
import time
from midi.config import *
from wav.myPWM import myPWM

AUDIO_PIN = 18  # Audio output pin

@asm_pio(set_init=PIO.OUT_LOW)
def debug_tone():
    wrap_target()
    set(pins, 1)   [29]  # Set pin high and delay
    set(pins, 0)   [29]  # Set pin low and delay
    wrap()

class DebugAudioTest:
    def __init__(self):
        print("Start PWM")
        pwm = myPWM(Pin(18))
        try:
            value = 0
            increment = 1
            while True:
                value = value % 256
                pwm.duty(value)
                if value == 0:
                    increment = increment * (-1)
                value += increment
                time.sleep_ms(1)
        except KeyboardInterrupt:
            pwm.deinit()
        print("End PWM")

        self.sm = StateMachine(0, debug_tone, freq=SAMPLE_RATE, set_base=Pin(AUDIO_PIN))
        print(f"PIO initialized with audio output on pin {AUDIO_PIN}")

    def play_tone(self, duration_ms):
        print(f"Starting to play tone for {duration_ms} ms")
        self.sm.active(1)
        start_time = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), start_time) < duration_ms:
            if time.ticks_diff(time.ticks_ms(), start_time) % 100 == 0:
                print(f"Tone playing for {time.ticks_diff(time.ticks_ms(), start_time)} ms")
            time.sleep_ms(10)  # Small delay to prevent busy waiting
        self.sm.active(0)
        print("Tone finished")

# Usage
audio_test = DebugAudioTest()

print("Playing test tone")
audio_test.play_tone(50000)  # Play tone for 50 seconds

print("Test complete")