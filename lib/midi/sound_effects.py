import math
from midi.config import SAMPLE_RATE

import array

class Delay:
    def __init__(self, delay_ms, feedback=0.5, sample_rate=44100):
        self.sample_rate = sample_rate
        max_samples = 5000  # Approx. 18.9 KB for 32-bit floats
        self.delay_samples = min(int(delay_ms * sample_rate / 1000), max_samples)
        self.buffer = array.array('f', [0] * self.delay_samples)
        self.write_pos = 0
        self.feedback = feedback

    def process(self, input_sample):
        # Read the delayed sample
        read_pos = (self.write_pos - 1) % self.delay_samples
        delayed_sample = self.buffer[read_pos]

        # Write to the buffer
        self.buffer[self.write_pos] = input_sample + self.feedback * delayed_sample
        self.write_pos = (self.write_pos + 1) % self.delay_samples

        # Mix the input with the delayed signal
        return input_sample + delayed_sample


class Chorus:
    def __init__(self, rate=1, depth=0.003, mix=0.5):
        self.buffer = [0] * int(0.05 * SAMPLE_RATE)  # 50ms maximum delay
        self.write_pos = 0
        self.rate = rate
        self.depth = depth
        self.mix = mix
        self.phase = 0

    def process(self, input_sample):
        # Write to buffer
        self.buffer[self.write_pos] = input_sample
        self.write_pos = (self.write_pos + 1) % len(self.buffer)

        # Calculate delay
        delay = self.depth * (math.sin(self.phase) + 1) / 2
        delay_samples = int(delay * SAMPLE_RATE)

        # Read from buffer
        read_pos = (self.write_pos - delay_samples) % len(self.buffer)
        delayed_sample = self.buffer[read_pos]

        # Update phase
        self.phase += 2 * math.pi * self.rate / SAMPLE_RATE

        # Mix dry and wet signals
        return input_sample * (1 - self.mix) + delayed_sample * self.mix

class SimpleReverb:
    def __init__(self, room_size=0.8, damping=0.5):
        self.room_size = room_size
        self.damping = damping
        self.delay_lines = [
            Delay(0.03, self.room_size),
            Delay(0.037, self.room_size),
            Delay(0.041, self.room_size),
            Delay(0.043, self.room_size)
        ]

    def process(self, input_sample):
        reverb = sum(delay.process(input_sample) for delay in self.delay_lines) / len(self.delay_lines)
        reverb *= (1 - self.damping)
        return input_sample * 0.5 + reverb * 0.5