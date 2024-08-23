import math

import rp2
from machine import Pin, mem32, PWM
from rp2 import PIO, StateMachine, DMA
import utime as time
from uarray import array
import uctypes

from midi.config import SAMPLE_RATE

# Define registers
PIO0_BASE = 0x50200000
PIO0_TXF0 = PIO0_BASE + 0x10

DMA_BASE = 0x50000000
CH0_READ_ADDR = DMA_BASE + 0x000
CH0_WRITE_ADDR = DMA_BASE + 0x004
CH0_TRANS_COUNT = DMA_BASE + 0x008
CH0_CTRL_TRIG = DMA_BASE + 0x00c
CTRL_ENABLE = 1 << 0
DATA_REQUEST_INDEX = 0  # Adjust this value based on your PIO SM configuration

# Constants for sine wave approximation
B = 4 / math.pi
C = -4 / (math.pi * math.pi)
P = 0.225
# OUT_PIN = 18

OUT_PIN = 18  # This is typically the onboard LED pin for Raspberry Pi Pico


@rp2.asm_pio(set_init=PIO.OUT_LOW)
def simple_tone():
    wrap_target()
    set(pins, 1)   [29]  # Set pin high and delay
    set(pins, 0)   [29]  # Set pin low and delay
    wrap()

class PIOSoundPlayer:
    def __init__(self, sample_rate=44100, buffer_size=256):
        self.sample_rate = sample_rate
        self.buffer_size = buffer_size
        self.buffer0 = array('I', [0] * buffer_size)
        self.buffer1 = array('I', [0] * buffer_size)
        self.current_buffer = 0
        self.buffers = [self.buffer0, self.buffer1]

        self.dma0 = None
        self.dma1 = None
        self.sm = None

        self.init_pio()
        # self.init_dma()

    def init_pio(self):
        self.sm = StateMachine(0, audio_tone, freq=125_000_000, set_base=Pin(OUT_PIN))
        # self.sm = StateMachine(0, audio_signal, freq=125_000_000, set_base=Pin(OUT_PIN))
        print(f"PIO initialized with audio output on pin {OUT_PIN}")

    def init_dma(self):
        self.dma0 = DMA()
        self.dma1 = DMA()

        pio_num, sm_num = 0, 0
        data_request_index = (pio_num << 3) + sm_num
        pio0_base_txf0 = 0x50200000 + 0x10

        ctrl0 = self.dma0.pack_ctrl(
            size=2,  # 32-bit transfers
            inc_read=True,
            inc_write=False,
            irq_quiet=False,
            bswap=False,
            treq_sel=data_request_index,
            chain_to=self.dma1.channel
        )
        self.dma0.config(
            count=self.buffer_size,
            read=self.buffer0,
            write=pio0_base_txf0,
            ctrl=ctrl0,
        )

        ctrl1 = self.dma1.pack_ctrl(
            size=2,
            inc_read=True,
            inc_write=False,
            irq_quiet=False,
            bswap=False,
            treq_sel=data_request_index,
            chain_to=self.dma0.channel
        )
        self.dma1.config(
            count=self.buffer_size,
            read=self.buffer1,
            write=pio0_base_txf0,
            ctrl=ctrl1,
        )

        self.dma0.irq(self.dma_handler)

    def dma_handler(self, dma):
        self.current_buffer = 1 - self.current_buffer
        self.fill_buffer(self.buffers[self.current_buffer])

    def fill_buffer(self, buffer):
        for i in range(self.buffer_size):
            sample = int((math.sin(2 * math.pi * 440 * i / self.sample_rate) * 0.5 + 0.5) * 2 ** 32)
            buffer[i] = sample

    def start(self):
        self.fill_buffer(self.buffer0)
        self.fill_buffer(self.buffer1)
        # self.dma0.active(1)


    def set_frequency(self, freq):
        # Calculate delay cycles. Subtract 6 to account for the instructions in the loop
        delay = max(1, int(125_000_000 / (2 * freq)) - 6)
        self.sm.put(delay)

    def play_tone(self, frequency, duration_ms):
        print(f"Playing tone: {frequency} Hz for {duration_ms} ms")
        self.set_frequency(frequency)
        time.sleep_ms(duration_ms)
        self.set_frequency(1)  # Set to very low frequency (almost off)

    def play_jump_sound(self):
        print("Playing jump sound")
        start_freq = 150
        end_freq = 300
        duration_ms = 200
        steps = 20

        step_duration = duration_ms // steps
        for i in range(steps):
            freq = start_freq + (end_freq - start_freq) * i // steps
            self.set_frequency(freq)
            time.sleep_ms(step_duration)

        self.set_frequency(1)  # Set to very low frequency (almost off)
        print("Jump sound finished")

    def stop(self):
        self.set_frequency(1)  # Set to a very low frequency (almost off)


    def test_tone(self):
        print("Playing test tone")
        self.play_tone(440, 1000)  # 440 Hz for 1 second
        print("Test tone finished")

    def blink_led(self, on_time_ms, off_time_ms, count=1):
        on_cycles = int(125_000 * on_time_ms)
        off_cycles = int(125_000 * off_time_ms)

        for _ in range(count):
            print(f"Blinking LED: ON for {on_time_ms}ms, OFF for {off_time_ms}ms")
            self.sm.put(on_cycles)
            self.sm.put(off_cycles)
            time.sleep_ms(on_time_ms + off_time_ms)

    def test_sequence(self):
        print("Starting test sequence")

        print("1. Single blink")
        self.blink_led(500, 500)
        time.sleep_ms(1000)

        print("2. Rapid blinks")
        self.blink_led(100, 100, 5)
        time.sleep_ms(1000)

        print("3. Long ON, short OFF")
        self.blink_led(1000, 200)
        time.sleep_ms(1000)

        print("4. Short ON, long OFF")
        self.blink_led(200, 1000)
        time.sleep_ms(1000)

        print("5. Varying pattern")
        for i in range(5):
            on_time = 100 * (i + 1)
            off_time = 100 * (5 - i)
            self.blink_led(on_time, off_time)

        print("Test sequence complete")

player = PIOSoundPlayer()

print("Playing test tone")
player.play_tone(440, 1000)  # Play 440 Hz for 1 second

time.sleep_ms(500)

print("Playing jump sound")
player.play_jump_sound()

print("Test complete")