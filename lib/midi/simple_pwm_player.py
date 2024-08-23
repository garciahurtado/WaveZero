import array
import math

from machine import PWM, Pin, mem32
from rp2 import PIO, StateMachine, DMA, asm_pio
import utime as time
from uctypes import addressof

# DMA constants
DMA_BASE = 0x50000000
CH0_READ_ADDR = DMA_BASE + 0x000
CH0_WRITE_ADDR = DMA_BASE + 0x004
CH0_TRANS_COUNT = DMA_BASE + 0x008
CH0_CTRL_TRIG = DMA_BASE + 0x00c
CH0_AL1_CTRL = DMA_BASE + 0x010
CH0_AL1_READ_ADDR = DMA_BASE + 0x014
CH0_AL1_WRITE_ADDR = DMA_BASE + 0x018
CH0_AL1_TRANS_COUNT = DMA_BASE + 0x01c
CH0_AL2_CTRL = DMA_BASE + 0x020
CH0_AL2_TRANS_COUNT = DMA_BASE + 0x024
CH0_AL3_CTRL = DMA_BASE + 0x028
CH0_AL3_WRITE_ADDR = DMA_BASE + 0x02c
CH0_AL3_TRANS_COUNT = DMA_BASE + 0x030
PIO0_BASE = 0x50200000
PIO0_BASE_TXF0 = PIO0_BASE + 0x10

pio_num = 0 # PIO program number
sm_num = 0 # State Machine number
DATA_REQUEST_INDEX = (pio_num << 3) + sm_num

@asm_pio(sideset_init=PIO.OUT_LOW, out_init=PIO.OUT_LOW, out_shiftdir=PIO.SHIFT_LEFT, autopull=True, pull_thresh=32)
def pwm_pio():
    pull(noblock)         .side(0)      # Pull from FIFO to OSR if available, else copy X to OSR.
    mov(x, osr)                         # Copy most-recently-pulled value back to scratch X
    mov(y, isr)                         # ISR contains PWM period. Y used as counter.

    label("countloop")
    jmp(x!=y, "noset")                  # Set pin high if X == Y, keep the two paths length matched
    jmp("skip")           .side(1)

    label("noset")
    nop()                           [9]         # Single dummy cycle to keep the two paths the same length
    label("skip")
    jmp(y_dec, "countloop")             # Loop until Y hits 0, then pull a fresh PWM value from FIFO


# @asm_pio(out_init=PIO.OUT_LOW, out_shiftdir=PIO.SHIFT_LEFT, autopull=True, pull_thresh=32)
# def pwm_pio():
#     # X is our PWM period (constant)
#     # Y is our bit depth (8 or 10)
#     pull(block)  # Pull PWM period into X
#     mov(x, osr)
#     pull(block)  # Pull bit depth into Y
#     mov(y, osr)
#
#     pull(block)  # Pull initial sample
#     mov(isr, osr)  # Store in ISR for later use
#
#     wrap_target()
#
#     mov(osr, isr)  # Move stored sample to OSR
#     jmp(y_dec, "bit_10")  # If Y == 10, it's 10-bit PWM
#     # 8-bit PWM
#     out(null, 24)  # Shift out top 24 bits (we only want bottom 8)
#     out(pins, 8)  # Output 8-bit PWM value
#     jmp("continue")
#     label("bit_10")
#     out(null, 22)  # Shift out top 22 bits (we only want bottom 10)
#     out(pins, 10)  # Output 10-bit PWM value
#     mov(y, 10)  # Reset Y to 10
#
#     label("continue")
#     mov(y, x)  # Reset counter to PWM period
#     label("pwm_loop")
#     jmp(y_dec, "pwm_loop")  # Delay for PWM period
#
#     pull(noblock)  # Try to pull next sample
#     mov(isr, osr)  # Store in ISR for next cycle
#
#     wrap()

class SimplePwmPlayer():
    PWM_TOP = 1024
    PWM_HALF = 1024 // 2
    LARGE_TOP = 32767 * 2
    LARGE_HALF = 32767

    def __init__(self, pin, sample_rate=4000, buffer_size=200):
        self.pin = pin
        self.sample_rate = sample_rate
        self.bit_depth = 8
        self.half_freq = sample_rate / 2
        self.pio_freq = 10000

        self.buffer_size = buffer_size
        self.buffer = array.array('H', [0] * buffer_size)

        self.DMA_0_CH = 0
        self.DMA_1_CH = 1

        self.dma0 = DMA()  # Use DMA channel 0
        self.dma1 = DMA()  # Use DMA channel 1
        self.setup_dma()

        # Configure PIO state machine
        self.sm = StateMachine(0, pwm_pio, freq=self.pio_freq, sideset_base=self.pin)

        # Calculate and set PWM period
        period = int(self.pio_freq / sample_rate) - 1
        self.sm.put(period)
        self.sm.exec("pull()")
        self.sm.exec("mov(isr, osr)")

        self.sm.active(1)

    def setup_dma(self):
        # DMA TX channel
        dma_ctrl = self.dma0.pack_ctrl(
            ring_size=10,
            ring_sel=True,
            inc_read=True,
            inc_write=False,
            high_pri=True,
            chain_to=self.DMA_1_CH)

        self.dma0.config(
            ctrl=dma_ctrl,
            read=self.buffer,
            write=PIO0_BASE_TXF0,
            count=self.buffer_size,
            trigger=False,
        )
        self.dma0.irq(PIO(0).irq(0))

        # DMA CTRL Channel
        dma_ctrl = self.dma1.pack_ctrl(
            ring_size=10,
            ring_sel=True,
            inc_read=False,
            inc_write=False,
            high_pri=True,
            chain_to=self.DMA_0_CH)

        self.dma1.config(
            ctrl=dma_ctrl,
            read=self.buffer,
            write=PIO0_BASE_TXF0,
            count=self.buffer_size,
            trigger=False,
        )

    def play(self, frequency, duration):
        samples = int(self.sample_rate * duration)
        self.dma0.active()

        for i in range(samples):
            # Generate sine wave and convert to PWM values
            value = int(32767 + 32767 * math.sin(2 * math.pi * frequency * i / self.sample_rate))
            self.buffer[i % self.buffer_size] = value

            # If buffer is full, wait for DMA to complete and restart
            if (i + 1) % self.buffer_size == 0:
                while mem32[CH0_CTRL_TRIG] & (1 << 24):  # Wait for DMA to complete
                    pass
                self.dma0.active(1)
                # self.dma()  # Restart DMA

    def stop(self):
        self.sm.active(0)

    def sine_wave(self, frequency, duration):
        samples = int(self.sample_rate * duration)
        for i in range(samples):
            value = int(32767 + 32767 * math.sin(2 * math.pi * frequency * i / self.sample_rate))
            yield value

class CircularBuffer:
    def __init__(self, size):
        self.buffer = array.array('H', [0] * size)
        self.size = size
        self.read_idx = 0
        self.write_idx = 0
        self.count = 0

    def write(self, value):
        if self.count < self.size:
            self.buffer[self.write_idx] = value
            self.write_idx = (self.write_idx + 1) % self.size
            self.count += 1
        else:
            raise BufferError("Buffer is full")

    def read(self):
        if self.count > 0:
            value = self.buffer[self.read_idx]
            self.read_idx = (self.read_idx + 1) % self.size
            self.count -= 1
            return value
        else:
            raise BufferError("Buffer is empty")

    def __len__(self):
        return self.count

    def is_full(self):
        return self.count == self.size

    def is_empty(self):
        return self.count == 0

