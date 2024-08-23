import math
import utime as time
from machine import Pin
from midi.adsr_envelope import ADSREnvelope as Envelope
from midi.config import SAMPLE_RATE
from midi.pio_sound_player import PIOSoundPlayer
from midi.synth import Synthesizer

class MidiPlayer:
    def __init__(self, output_pin=18):
        self.output_pin = Pin(output_pin)
        self.sound_out = PIOSoundPlayer()
        self.play_speed = 100  # 100 percent. Anything lower will slow it down, higher will speed it up

        # Create an ADSR envelope
        self.envelope = Envelope(attack_ms=50, decay_ms=100, sustain_level=0.7, release_ms=200)

        self.init_envelopes()
        self.set_instrument('piano')
        self.synth = Synthesizer(max_voices=4)

        self.sound_out.test_sequence()
        self.sound_out.test_tone()


    def generate_tone_samples(self, frequency, duration_ms):
        num_samples = int(SAMPLE_RATE * duration_ms / 1000)
        for i in range(num_samples):
            t = i / SAMPLE_RATE
            sample = math.sin(2 * math.pi * frequency * t)
            envelope_value = self.envelope.get_value()
            yield sample * envelope_value

    def play_tone(self, frequency, duration_ms):
        sample_generator = self.generate_tone_samples(frequency, duration_ms)
        try:
            self.sound_out.play_sample_generator(sample_generator, duration_ms)
        except Exception as e:
            print(f"Error playing tone: {e}")
        finally:
            self.sound_out.stop()
            time.sleep_ms(10)  # Small delay to allow for reset

    def play_melody(self, notes):
        for note, duration in notes:
            print(f"Playing {note} for {duration}")

            self.play_tone(int(note), duration)
            time.sleep_ms(int(duration * 1.1))  # Add a small gap between notes
    def init_envelopes(self):
        envelopes = {
            'piano': Envelope(attack_ms=10, decay_ms=100, sustain_level=0.7, release_ms=300),
            'organ': Envelope(attack_ms=20, decay_ms=20, sustain_level=0.8, release_ms=200),
            'strings': Envelope(attack_ms=100, decay_ms=200, sustain_level=0.7, release_ms=500),
            'pad': Envelope(attack_ms=500, decay_ms=1000, sustain_level=0.8, release_ms=2000),
            'pluck': Envelope(attack_ms=5, decay_ms=100, sustain_level=0, release_ms=10),
            'brass': Envelope(attack_ms=50, decay_ms=100, sustain_level=0.8, release_ms=200),
            'percussion': Envelope(attack_ms=5, decay_ms=50, sustain_level=0, release_ms=50),
            'soft_pad': Envelope(attack_ms=1000, decay_ms=2000, sustain_level=0.5, release_ms=3000),
            'snare': Envelope(attack_ms=2, decay_ms=100, sustain_level=0.1, release_ms=100),
            'bass': Envelope(attack_ms=20, decay_ms=100, sustain_level=0.6, release_ms=150),
            'bell': Envelope(attack_ms=1, decay_ms=500, sustain_level=0, release_ms=1000),
            'flute': Envelope(attack_ms=50, decay_ms=100, sustain_level=0.7, release_ms=100),
            'staccato': Envelope(attack_ms=5, decay_ms=10, sustain_level=0.8, release_ms=10),
            'swell': Envelope(attack_ms=1000, decay_ms=100, sustain_level=1, release_ms=1000),
            'tremolo': Envelope(attack_ms=20, decay_ms=20, sustain_level=0.8, release_ms=20)
        }

        self.envelopes = envelopes
        return self.envelopes

    def set_instrument(self, instr):
        print(f"Changing instrument to {instr}")
        self.envelope = self.envelopes[instr]

    def stop(self):
        self.sound_out.stop()

    def resume(self):
        self.sound_out.resume()

    def __del__(self):
        self.stop()