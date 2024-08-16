import math

import rp2
from machine import Pin, mem32
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

# Optimized PIO program for audio output
@rp2.asm_pio(out_init=PIO.OUT_LOW, sideset_init=PIO.OUT_LOW, out_shiftdir=PIO.SHIFT_RIGHT, autopull=True, pull_thresh=32)
def audio_pio():
    wrap_target()
    out(pins, 1)                    .side(0)    [2]
    jmp(not_osre, "output_loop")
    nop()                           .side(1)    [2]
    wrap()

    label("output_loop")
    out(pins, 1)                    .side(1)    [2]
    jmp(not_osre, "output_loop")
    nop()                           .side(0)    [2]


class PIOSoundPlayer:
    dma0: DMA = None
    dma1: DMA = None
    dma0_active = True
    dma1_active = False
    dma_tx_count = 256
    buffer0 = None
    buffer1 = None
    framebuf0 = None
    framebuf1 = None
    read_buffer = None
    write_buffer = None
    write_framebuf = None
    read_framebuf = None
    swap_ready = False
    fps = None
    paused = True
    curr_read_addr = False


    def __init__(self, pin, sample_rate=44100, buffer_size=256):
        self.sample_rate = sample_rate
        # freq = sample_rate * 2
        # freq = 62500000
        freq = 44100 * 4

        self.freq = int(freq)

        self.pin = Pin(pin)

        self.buffer_size = buffer_size
        self.buffer0 = array('I', [0] * buffer_size)  # 32-bit unsigned integer array
        self.buffer1 = array('I', [0] * buffer_size)
        self.current_buffer = 0
        self.buffers = [self.buffer0, self.buffer1]

        self.playback_active = False

        self.dma0 = None
        self.dma1 = None
        self.init_dma()
        self.init_pio_spi()

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
            read=uctypes.addressof(self.buffer0),
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
            read=uctypes.addressof(self.buffer1),
            write=pio0_base_txf0,
            ctrl=ctrl1,
        )

        self.dma0.irq(self.dma_handler)

    def dma_handler(self, dma):
        # Switch to the other buffer
        self.current_buffer = 1 - self.current_buffer
        # Fill the next buffer
        self.fill_buffer(self.buffers[self.current_buffer])

    def _init_dma(self):
        # Set up DMA channels
        self.dma0 = DMA()
        self.dma1 = DMA()

        # Configure DMA channel 0
        ctrl0 = self.dma0.pack_ctrl(
            size=2,  # 32-bit transfers
            inc_read=True,
            inc_write=False,
            irq_quiet=False,
            bswap=False,  # No byte swap needed for our use case
            treq_sel=DATA_REQUEST_INDEX,
            chain_to=self.dma1.channel
        )
        self.dma0.config(
            count=self.buffer_size,
            read=self.buffers[0],
            write=PIO0_TXF0,
            ctrl=ctrl0,
        )

        # Configure DMA channel 1 (for ping-pong buffer)
        ctrl1 = self.dma1.pack_ctrl(
            size=2,
            inc_read=True,
            inc_write=False,
            irq_quiet=False,
            bswap=False,
            treq_sel=DATA_REQUEST_INDEX,
            chain_to=self.dma0.channel
        )
        self.dma1.config(
            count=self.buffer_size,
            read=self.buffers[1],
            write=PIO0_TXF0,
            ctrl=ctrl1,
        )

        # Set up interrupt for DMA channel 0
        # self.dma0.irq(handler=self.swap_buffers, hard=False)

        # Set starting alias to each buffer
        self.write_buffer = self.audio_buffer0
        self.read_buffer = self.audio_buffer1

        self.write_framebuf = self.audio_buffer0
        self.read_framebuf = self.audio_buffer1

        self.read_addr = uctypes.addressof(self.read_buffer)
        self.read_addr_buf = self.read_addr.to_bytes(4, "little")

        self.write_addr = uctypes.addressof(self.write_buffer)
        self.write_addr_buf = self.write_addr.to_bytes(4, "little")

        self.curr_read_buf = self.read_addr_buf

    def dma_handler(self, dma):
        # Switch to the other buffer
        self.current_buffer_id = 1 - self.current_buffer_id
        # Fill the next buffer
        self.fill_buffer(self.buffers[self.current_buffer_id])
        # Update DMA read address
        mem32[CH0_READ_ADDR] = int.from_bytes(self.curr_read_buf, "little")

    def _fill_buffer(self, buffer):
        for i in range(self.buffer_size):
            try:
                sample1 = next(self.sample_generator)
                sample2 = next(self.sample_generator)
            except StopIteration:
                buffer[i] = 0
                continue
            combined_sample = (int((sample1 + 1) * 32767.5) & 0xFFFF) | ((int((sample2 + 1) * 32767.5) & 0xFFFF) << 16)
            buffer[i] = combined_sample

    def swap_buffers(self, _):
        self.read_addr_buf, self.write_addr_buf = self.write_addr_buf, self.read_addr_buf
        self.read_framebuf, self.write_framebuf = self.write_framebuf, self.read_framebuf

        """ Now that we've flipped the buffers, reprogram the DMA so that it will start reading from the 
        correct buffer (the one that just finished writing) in the next iteration """

        if self.curr_read_buf == self.read_addr_buf:
            self.curr_read_buf = self.write_addr_buf
        else:
            self.curr_read_buf = self.read_addr_buf


        # Kickoff the DMA channel automatically by assigning it a read address
        self.dma1.read = uctypes.addressof(self.curr_read_buf)

    def init_pio_spi(self):
        # Define the pins
        pin_out = self.pin

        # Set up the PIO state machine
        # freq = 120 * 1000 * 1000
        # freq = 62500000
        # freq = int(SAMPLE_RATE * 0.1)

        self.sm = StateMachine(0)

        # pin_out.value(0) # Pull down to enable CS
        # pin_out.value(1) # D/C = 'data'

        self.sm = StateMachine(0, audio_pio, freq=44100 * 4, sideset_base=Pin(15))

        # self.sm_debug(sm)
        self.sm.active(1)

    # Optimized sine function using Taylor series approximation
    def fast_sine(self, x):
        y = B * x + C * x * abs(x)
        y = P * (y * abs(y) - y) + y
        return y

    def sine_samples(self, freq, duration_ms, volume=1, sample_rate=44100):
        num_samples = int(sample_rate * duration_ms / 1000)
        samples = array("I", [0] * 32)  # Pre-allocate a small buffer

        for i in range(num_samples):
            # Generate one sample at a time
            t = i / sample_rate
            sample = int((self.fast_sine(2 * math.pi * freq * t) * 0.5 + 0.5) * volume * 2 ** 32)
            samples[i % 32] = sample

            # Yield the sample when the buffer is full
            if i % 32 == 31:
                yield samples

        # Yield any remaining samples
        if num_samples % 32 != 0:
            yield samples[:num_samples % 32]

    # Function to play audio samples
    def play_audio(self, samples, duration_ms):
        start_time = time.ticks_ms()
        for sample in samples:
            if time.ticks_diff(time.ticks_ms(), start_time) >= duration_ms:
                break
            self.sm.put(sample)
            time.sleep_us(20)  # Adjust this delay as needed

    def jump_sound(self):
        print("Playing JUMP sound")
        freq = 440
        duration_ms = 50
        samples = (next(self.sine_samples(freq + i * 20, 1)) for i in range(duration_ms))
        self.play_audio(samples, duration_ms)

    def coin_sound(self):
        print("Playing COIN sound")
        # High-pitched short beep
        self.play_audio(self.sine_samples(1000, 50), 50)
        # 50ms silence
        self.play_audio((0 for _ in range(2205)), 50)
        # Higher pitched longer beep
        self.play_audio(self.sine_samples(1500, 100), 100)

    def test_tone(self):
        print("Playing test tone")
        freq = 440  # A4 note
        duration_ms = 1000  # 1 second
        samples = (int((math.sin(2 * math.pi * freq * i / self.sample_rate) * 0.5 + 0.5) * 2 ** 32)
                   for i in range(int(self.sample_rate * duration_ms / 1000)))
        self.play_audio(samples, duration_ms)
        print("Test tone finished")

    def play_sample_generator(self, sample_generator, duration_ms):
        print(f"Starting playback for {duration_ms}ms")
        start_time = time.ticks_ms()
        samples_played = 0
        expected_samples = int(self.sample_rate * duration_ms / 1000)
        self.playback_active = True

        while samples_played < expected_samples and self.playback_active:
            buffer = self.buffers[self.current_buffer_id]
            for i in range(self.buffer_size):
                if samples_played >= expected_samples:
                    buffer[i] = 0
                    continue
                try:
                    sample1 = next(sample_generator)
                    sample2 = next(sample_generator)
                    samples_played += 2
                except StopIteration:
                    print(f"Generator stopped after {samples_played} samples")
                    buffer[i] = 0
                    self.playback_active = False
                    break

                combined_sample = (int((sample1 + 1) * 32767.5) & 0xFFFF) | ((int((sample2 + 1) * 32767.5) & 0xFFFF) << 16)
                buffer[i] = combined_sample

            # self.dma0.active(1)
            self.current_buffer_id = 1 - self.current_buffer_id  # Switch buffers

            # Wait for DMA to finish
            while self.sm.active():
                if time.ticks_diff(time.ticks_ms(), start_time) >= duration_ms:
                    self.playback_active = False
                    break

        print(f"Finished playback after {time.ticks_diff(time.ticks_ms(), start_time)}ms")
        self.stop()

    def _stop(self):
        print("Stopping PIOSoundPlayer")
        self.playback_active = False
        # self.dma0.active(0)
        # self.dma1.active(0)
        self.sm.active(0)
        # Clear the buffers
        for buffer in self.buffers:
            for i in range(self.buffer_size):
                buffer[i] = 0

    def fill_buffer(self, buffer):
        for i in range(self.buffer_size):
            sample = int((math.sin(2 * math.pi * 440 * i / self.sample_rate) * 0.5 + 0.5) * 2**32)
            buffer[i] = sample

    def start(self):
        self.fill_buffer(self.buffer0)
        self.fill_buffer(self.buffer1)
        self.dma0.active(1)

    def stop(self):
        self.dma0.active(0)
        self.dma1.active(0)

    def _fill_buffer(self, buffer):
        for i in range(self.buffer_size):
            if self.samples_played >= self.total_samples:
                buffer[i] = 0
                continue
            try:
                sample1 = next(self.sample_generator)
                sample2 = next(self.sample_generator)
                self.samples_played += 2
            except StopIteration:
                buffer[i] = 0
                continue
            combined_sample = (int((sample1 + 1) * 32767.5) & 0xFFFF) | ((int((sample2 + 1) * 32767.5) & 0xFFFF) << 16)
            buffer[i] = combined_sample

    def _stop(self):
        # self.dma0.active(0)
        # self.dma1.active(0)
        self.sm.active(0)
        # Clear the buffers
        for buffer in self.buffers:
            for i in range(self.buffer_size):
                buffer[i] = 0
        self.samples_played = 0


    def resume(self):
        self.sm.active(1)
        # self.dma0.active(1)