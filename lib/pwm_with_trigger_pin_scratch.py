import rp2
from machine import Pin
import time
from uarray import array
from uctypes import addressof

PIO_FREQ = 1_000_000
PIO_PGM_CYCLES = 8
DUTY_MAX = 2800

# DMA constants
DMA_BASE = 0x50000000
CH0_READ_ADDR = DMA_BASE + 0x000
CH0_WRITE_ADDR = DMA_BASE + 0x004
CH0_TRANS_COUNT = DMA_BASE + 0x008
CH0_CTRL_TRIG = DMA_BASE + 0x00c
CH0_AL1_CTRL = DMA_BASE + 0x010

PIO0_BASE = 0x50200000
PIO0_TXF0 = PIO0_BASE + 0x10

BUFFER_SIZE = 256
DREQ_PIO0_TX0 = 0x0
AUDIO_RATE = 44100
max_amp = 33000

@rp2.asm_pio(set_init=rp2.PIO.OUT_LOW, autopull=True, pull_thresh=32)
def audio_pwm():
    pull(ifempty, noblock)              # Pull 16-bit value from FIFO
    mov(x, osr)                         # Move 16 bits to X register

    wrap_target()
    mov(y, x)                           # Copy pulse width to Y

    label("pwm_loop")
    jmp(y, "pin_high")                  # Jump if Y != 0
    jmp("pin_low")                      # Jump to pin_low if Y == 0

    label("pin_high")
    set(pins, 1)      [16]                  # Set pin high
    jmp(y_dec, "pin_high")              # Decrement Y and loop

    label("pin_low")
    set(pins, 0)           [16]                # Set pin low
    mov(y, x)                           # Reset Y to X for consistent timing
    jmp(y_dec, "pin_low")               # Decrement Y and loop for low period

    wrap()                              # Loop back to start
"""
    pull(noblock)       .side(0)    # Pull from FIFO to OSR if available, else copy X to OSR.
    mov(x, osr)                     # Copy most-recently-pulled value back to scratch X
    mov(y, isr)                     # ISR contains PWM period. Y used as counter.

    label("countloop")
    jmp(x != y, "noset")            # Set pin high if X == Y, keep the two paths length matched
    jmp("skip")         .side(1)

    label("noset")
    nop()               [1]         # Single dummy cycle to keep the two paths the same length
    label("skip")
    jmp(y_dec, "countloop")         # Loop until Y hits 0, then pull a fresh PWM value from FIFO
"""


sm = rp2.StateMachine(0, audio_pwm, freq=PIO_FREQ, set_base=Pin(18))

def gen_square_wave(buffer_size, min_val, max_val):
    half_size = buffer_size // 2
    buffer = []
    for i in range(buffer_size):
        if i < half_size:
            buffer.append(max_val)
        else:
            buffer.append(min_val)
    return array('L', buffer)  # 'H' for 16-bit unsigned integers

# Usage

def play_tone(frequency, duration, waveform):
    start_time = time.ticks_us()
    phase_accumulator = 0
    wave_size = len(waveform)
    phase_increment = int(frequency * wave_size * max_amp / AUDIO_RATE)

    while time.ticks_diff(time.ticks_us(), start_time) < duration * 1000000:
        index = (phase_accumulator >> 16) & (wave_size - 1)
        duty = waveform[index]
        set_duty(duty)

        phase_accumulator += phase_increment
        time.sleep_us(int(1000000 / AUDIO_RATE))

dma_ch0 = None

def setup_dma(buffer_addr):
    # Data channel (CH0)
    global dma_ch0
    dma_ch0 = rp2.DMA()

    # Control channel (CH1)
    dma_ch1 = rp2.DMA()

    buffer_addr_bytes = buffer_addr.to_bytes(4, "little")


    # Configure data channel (CH0)
    ctrl0 = dma_ch0.pack_ctrl(
        enable=True,
        ring_size=8,  # log2(BUFFER_SIZE)
        ring_sel=0,  # Apply ring to write address
        treq_sel=DREQ_PIO0_TX0,
        chain_to=1,  # Chain to CH1
        size=2,  # 32-bit transfers
        inc_read=True,
        inc_write=False,
        bswap=False,
    )

    dma_ch0.config(
        read=buffer_addr,
        write=PIO0_TXF0,
        count=BUFFER_SIZE,
        ctrl=ctrl0,
    )

    # Configure control channel (CH1)
    ctrl1 = dma_ch1.pack_ctrl(
        enable=False,
        chain_to=0,  # Chain back to CH0
        size=2,  # 32-bit transfers
        inc_read=False,
        inc_write=False,
    )

    # We're just transferring the read address back to CH0
    dma_ch1.config(
        read=buffer_addr_bytes,
        write=DMA_BASE,
        count=1,
        ctrl=ctrl1,
    )



    # Configure read address increment (AL1)
    # dma_ch0.channel_config(channel, 1, read=phase_increment, write=0, count=0)
    #
    # # Configure transfer count (AL2)
    # dma_ch0.channel_config(channel, 2, read=0, write=0, count=buffer_size - 1)

    # CH0_READ_ADDR = DMA_BASE + channel * 0x40
    # CH0_WRITE_ADDR = CH0_READ_ADDR + 0x4
    # CH0_TRANS_COUNT = CH0_READ_ADDR + 0x8
    # CH0_CTRL_TRIG = CH0_READ_ADDR + 0xC
    # CH0_AL1_CTRL = CH0_READ_ADDR + 0x10
    # CH0_AL1_READ_ADDR = CH0_READ_ADDR + 0x14
    # CH0_AL1_WRITE_ADDR = CH0_READ_ADDR + 0x18
    # CH0_AL2_CTRL = CH0_READ_ADDR + 0x1C
    # CH0_AL2_TRANS_COUNT = CH0_READ_ADDR + 0x20
    # CH0_AL3_CTRL = CH0_READ_ADDR + 0x24
    # CH0_AL3_WRITE_ADDR = CH0_READ_ADDR + 0x28
    #
    # mem32[CH0_READ_ADDR] = buffer_address
    # mem32[CH0_WRITE_ADDR] = PIO0_TXF0
    # mem32[CH0_TRANS_COUNT] = 1
    #
    # # Configure main control register
    # ctrl = 0x3b000000 | (channel << 11)  # Chain to next channel, no IRQ, 8-bit transfers
    # mem32[CH0_CTRL_TRIG] = ctrl
    #
    # # Configure AL1 (Read Address)
    # mem32[CH0_AL1_CTRL] = 0x40000000  # Enable
    # mem32[CH0_AL1_READ_ADDR] = phase_increment
    #
    # # Configure AL2 (Transfer Count)
    # mem32[CH0_AL2_CTRL] = 0xC0000000  # Enable, wrap
    # mem32[CH0_AL2_TRANS_COUNT] = buffer_size - 1
    #
    # # Configure AL3 (Write Address)
    # mem32[CH0_AL3_CTRL] = 0x80000000  # Enable
    # mem32[CH0_AL3_WRITE_ADDR] = PIO0_TXF0

def set_duty(duty):
    global sm

    # duty is a value between 0 and 255
    # sm.put(duty)


try:
    # wave = gen_square_wave(BUFFER_SIZE, 0, max_amp)
    wave = gen_square_wave(BUFFER_SIZE, 0, 32000)  # Full 16-bit range

    print("Playing wave...")

    sm.active(1)
    setup_dma(addressof(wave))
    dma_ch0.active(1)

    while True:
        time.sleep(1)  # Keep the program running


except KeyboardInterrupt:
    sm.active(0)