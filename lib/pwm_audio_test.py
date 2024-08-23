import sys

from machine import Pin, PWM
import math
import time
from midi.config import *

AUDIO_PIN = 18  # Audio output pin
# PWM_FREQ = SAMPLE_RATE * 1000 # 500 kHz PWM frequency

PWM_FREQ = SAMPLE_RATE * 1024
MIN_SAMPLES_PER_CYCLE = 10  # Minimum number of samples per cycle for good quality
MAX_SAMPLE_RATE = 44100  # Maximum sample rate (standard audio)
MAX_VOLUME = 65535  # Maximum PWM duty cycle

class PWMAudioGenerator:
    def __init__(self, pin_number):
        self.pwm = PWM(Pin(pin_number))
        self.pwm.freq(PWM_FREQ)
        self.pwm.duty_u16(0)  # Start with 0% duty cycle (silent)
        # self.sample_period_us = 100000 // SAMPLE_RATE

        print(f"PWM Audio Generator initialized on pin {pin_number}")
        print(f"Sample Rate: {SAMPLE_RATE} Hz, PWM Frequency: {PWM_FREQ} Hz")

    def sine_wave(self, t, freq):
        freq = freq
        t = t / 10
        return int((math.sin(2 * math.pi * freq * t) + 1) * 32767)

    def square_wave(self, t, freq):
        freq = freq
        return int (65535) if (t * freq) % 1 < 0.5 else 0

    def calculate_sample_rate(self, frequency):
        sample_rate = frequency * MIN_SAMPLES_PER_CYCLE
        return min(sample_rate, MAX_SAMPLE_RATE)

    def set_volume(self, percentage):
        """Set volume as a percentage (0-100)"""
        self.volume = int(MAX_VOLUME * (percentage / 100))
        print(f"Volume set to {percentage}%")

    def play_tone(self, frequency, duration_ms):
        print(f"Playing tone: {frequency} Hz for {duration_ms} ms")
        period_us = 1000000 // frequency
        half_period_us = period_us // 2
        cycles = (duration_ms * 1000) // period_us

        for _ in range(cycles):
            start = time.ticks_us()
            self.pwm.duty_u16(self.volume)
            while time.ticks_diff(time.ticks_us(), start) < half_period_us:
                pass
            self.pwm.duty_u16(0)
            while time.ticks_diff(time.ticks_us(), start) < period_us:
                pass

        self.pwm.duty_u16(0)  # Ensure it ends silently
        print("Tone finished")

    def play_jump_sound(self, start_freq=150, end_freq=300, duration_ms=200):
        print(f"Playing jump sound from {start_freq} Hz to {end_freq} Hz over {duration_ms} ms")
        steps = 100
        step_duration_us = (duration_ms * 1000) // steps

        for i in range(steps):
            current_freq = start_freq + (end_freq - start_freq) * i // steps
            period_us = 1000000 // current_freq
            half_period_us = period_us // 2
            step_end = time.ticks_add(time.ticks_us(), step_duration_us)

            while time.ticks_diff(step_end, time.ticks_us()) > 0:
                cycle_start = time.ticks_us()
                self.pwm.duty_u16(self.volume)
                while time.ticks_diff(time.ticks_us(), cycle_start) < half_period_us:
                    pass
                self.pwm.duty_u16(0)
                while time.ticks_diff(time.ticks_us(), cycle_start) < period_us:
                    pass

        self.pwm.duty_u16(0)  # Ensure it ends silently
        print("Jump sound finished")

    def stop(self):
        self.pwm.duty_u16(0)  # Silent
        print("Audio stopped")

# Usage
audio_gen = PWMAudioGenerator(AUDIO_PIN)

print("Setting volume to 50%")
audio_gen.set_volume(50)

audio_gen.play_jump_sound()
time.sleep_ms(500)

audio_gen.stop()

print("Playing 440 Hz test tone")
audio_gen.play_tone(440, 2000)  # Play 440 Hz tone for 3 seconds

time.sleep_ms(1000)

print("Playing 880 Hz test tone")
audio_gen.play_tone(880, 2000)  # Play 880 Hz tone for 3 seconds

time.sleep_ms(1000)

print("Test complete")
sys.exit(0)