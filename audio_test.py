import machine
import sys
import utime
import math
from midi.config import *
from midi.midi_player import MidiPlayer
from test_midi import get_melody


# Define a sine wave function
def sine_wave(freq, sample_rate=44100, amplitude=100):
    period = int(sample_rate / freq)
    return [int(amplitude * math.sin(2 * math.pi * i / period)) for i in range(period)]


# Configure PWM for audio output
pwm = machine.PWM(machine.Pin(25))  # Assuming GP25 is connected to a speaker/buzzer
pwm.freq(44100)  # Set PWM frequency to 44.1 kHz


def play_tone(frequency, duration_ms):
    wave = sine_wave(frequency)
    end_time = utime.ticks_add(utime.ticks_ms(), duration_ms)

    while utime.ticks_diff(end_time, utime.ticks_ms()) > 0:
        for sample in wave:
            pwm.duty_u16(int(sample + 32768))
            utime.sleep_us(int(1000000 / SAMPLE_RATE))  # Sleep for one sample period
            # utime.sleep_us(100)  # Adjust this delay if needed


def debug_synth2():
    player = MidiPlayer()

    print("Starting to play melody using MidiPlayer")
    melody = get_melody()

    for frequency, duration in melody:
        print(f"Playing {frequency:.2f} Hz for {duration} ms")
        player.play_tone(int(frequency), duration)
        utime.sleep_ms(50)  # Short pause between notes

    print("Finished playing melody")

def debug_tones():
    print("Starting improved audio test...")
    print("You should hear a sequence of clear tones.")

    player = MidiPlayer()

    # Play a sequence of tones
    frequencies = [262, 330, 392, 523]  # C4, E4, G4, C5
    for freq in frequencies:
        print(f"Playing {freq} Hz")
        player.play_tone(freq, 250)  # Play each tone for 500 ms
        utime.sleep_ms(100)  # Pause between tones

    print("Audio test complete.")
    player.reset()  # Clean up PWM

if __name__ != '__main__':
    # debug_tones()
    sys.exit(1)