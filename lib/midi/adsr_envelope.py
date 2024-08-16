import math
import utime
from midi.config import SAMPLE_RATE


class ADSREnvelope:
    def __init__(self, attack_ms, decay_ms, sustain_level, release_ms, sample_rate=SAMPLE_RATE):
        self.sample_rate = sample_rate
        self.attack_samples = self._ms_to_samples(attack_ms)
        self.decay_samples = self._ms_to_samples(decay_ms)
        self.sustain_level = sustain_level
        self.release_samples = self._ms_to_samples(release_ms)
        self.state = 'idle'
        self.current_sample = 0
        self.release_start_sample = None

    def _ms_to_samples(self, ms):
        return int(ms * self.sample_rate / 1000)

    def get_value(self):
        if self.state == 'idle':
            return 0

        if self.state == 'attack':
            if self.current_sample < self.attack_samples:
                value = self.current_sample / self.attack_samples
            else:
                self.state = 'decay'
                value = 1

        if self.state == 'decay':
            decay_progress = (self.current_sample - self.attack_samples) / self.decay_samples
            if decay_progress < 1:
                value = 1 - (1 - self.sustain_level) * decay_progress
            else:
                self.state = 'sustain'
                value = self.sustain_level

        if self.state == 'sustain':
            value = self.sustain_level

        if self.state == 'release':
            release_progress = (self.current_sample - self.release_start_sample) / self.release_samples
            if release_progress < 1:
                value = self.sustain_level * (1 - release_progress)
            else:
                self.state = 'idle'
                value = 0

        self.current_sample += 1
        return value

    def start(self):
        self.state = 'attack'
        self.current_sample = 0
        self.release_start_sample = None

    def release(self):
        if self.state != 'idle':
            self.state = 'release'
            self.release_start_sample = self.current_sample


class Voice:
    def __init__(self, frequency, waveform='sine'):
        self.frequency = frequency
        self.phase = 0
        self.active = True
        self.waveform = waveform
        self.sample_rate = SAMPLE_RATE
        self.envelope = ADSREnvelope(attack_ms=100, decay_ms=100, sustain_level=0.7, release_ms=200,
                                     sample_rate=SAMPLE_RATE)
        self.start_sample = 0
        self.current_sample = 0

    def get_sample(self):
        if not self.active:
            return 0

        # Generate waveform
        if self.waveform == 'sine':
            sample = math.sin(self.phase)
        elif self.waveform == 'square':
            sample = 1 if self.phase % (2 * math.pi) < math.pi else -1
        elif self.waveform == 'sawtooth':
            sample = (self.phase % (2 * math.pi)) / math.pi - 1
        else:
            sample = 0

        self.phase += 2 * math.pi * self.frequency / self.sample_rate
        # return sample

        # Apply envelope
        # envelope_value = self.envelope.get_value()
        self.current_sample += 1

        # return sample * envelope_value
        return sample

    def release(self):
        self.envelope.release()


