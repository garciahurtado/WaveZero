import math

import rp2
from machine import Pin
import time
from uarray import array
from uctypes import addressof
DUTY_MAX = 36000

# DMA constants
DMA_BASE = 0x50000000
CH0_READ_ADDR = DMA_BASE + 0x000
CH0_WRITE_ADDR = DMA_BASE + 0x004
CH0_TRANS_COUNT = DMA_BASE + 0x008
CH0_CTRL_TRIG = DMA_BASE + 0x00c
CH0_AL1_CTRL = DMA_BASE + 0x010

PIO0_BASE = 0x50200000
PIO0_TXF0 = PIO0_BASE + 0x10

BUFFER_SIZE = 128
DREQ_PIO0_TX0 = 0x0
SAMPLE_RATE = 44100
MAX_AMP = 512

# PIO_FREQ = 1_000_000
# PIO_FREQ = 340_000  # PIO frequency
PIO_FREQ = 100_000  # PIO frequency
NUM_INSTR = 1

PWM_PERIOD = MAX_AMP
to_micro = 1000000

wave = None

dma_ch0 = None
dma_ch1 = None

@rp2.asm_pio(set_init=rp2.PIO.OUT_LOW, autopull=True, pull_thresh=16)
def audio_pwm():
    pull(noblock)                  # Pull 16-bit value from FIFO
    mov(x, osr)             # Move value to X register
    mov(y, isr)             # Load PWM period from ISR (assume it's preloaded with 65535)

    label("loop")
    jmp(x_not_y, "skip")
    set(pins, 1)         [2]# Set pin high if X >= Y
    nop()       [16]
    nop()       [16]
    jmp("continue")

    label("skip")
    set(pins, 0)        [1] # Set pin low if X < Y

    label("continue")
    jmp(y_dec, "loop")      # Decrement Y and loop

sm = rp2.StateMachine(0, audio_pwm, freq=500_000, set_base=Pin(18))
sm.put(PWM_PERIOD)  # Preload the ISR with the PWM period
sm.exec("pull()")
sm.exec("out(isr, 32)")
sm.active(1)

def gen_square_wave(buffer_size, min_val, max_val):
    half_size = buffer_size // 2
    buffer = []
    for i in range(buffer_size):
        if i < half_size:
            buffer.append(max_val)
        else:
            buffer.append(min_val)
    return array('B', buffer)  # 'H' for 16-bit unsigned integers

def gen_sine_wave(buffer_size, freq, sample_rate):
    buffer = array('B', [0] * buffer_size)
    for i in range(buffer_size):
        t = i / sample_rate
        value = int((math.sin(2 * math.pi * freq * t) + 1)) * MAX_AMP
        # value = int(value - (MAX_AMP / 2)) # normalize
        print(f"w: {value}")
        buffer[i] = value
    return buffer


def play_tone(frequency, duration, waveform):
    global dma_ch0, dma_ch1, sm

    # sm.put(PWM_PERIOD // frequency)  # Preload the ISR with the PWM period
    # sm.exec("pull()")
    # sm.exec("out(isr, 32)")

    start_time = time.ticks_ms()
    phase_accumulator = 0
    wave_size = len(waveform)
    phase_increment = (frequency * wave_size * 65536) // SAMPLE_RATE
    phase_increment = phase_increment % wave_size

    print(f"Phase inc: {phase_increment}")

    new_wave = array('B', [0] * BUFFER_SIZE)
    buffer_index = 0

    for i in range(BUFFER_SIZE):
        phase = phase_accumulator >> 16
        index = int(phase % BUFFER_SIZE)
        new_wave[i] = waveform[index]
        phase_accumulator += phase_increment


    # Update DMA buffer
    new_wave_addr = addressof(new_wave)
    dma_ch1.read = new_wave_addr.to_bytes(4, "little")
    dma_ch0.active(False)
    dma_ch1.active(True)

    start = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), start) < (start_time + duration):
        pass

    # Ensure DMA channels are inactive after playing
    dma_ch0.active(False)
    dma_ch1.active(False)

def flag_dma0():
    print("FLAG DMA0")
def flag_dma1():
    print("FLAG DMA1")

def setup_dma(buffer_addr):
    # Data channel (CH0)
    global dma_ch0
    global dma_ch1


    dma_ch0 = rp2.DMA()
    dma_ch0.irq(handler=flag_dma0)

    # Control channel (CH1)
    dma_ch1 = rp2.DMA()
    dma_ch0.irq(handler=flag_dma1)

    buffer_addr_bytes = buffer_addr.to_bytes(4, "little")

    # Configure data channel (CH0)
    ctrl0 = dma_ch0.pack_ctrl(
        enable=True,
        ring_size=int(math.log2(BUFFER_SIZE)),  # Enable ring buffer
        ring_sel=1,  # Apply ring to read address
        treq_sel=DREQ_PIO0_TX0,
        chain_to=1,  # Chain to CH1
        size=1,  # 16 bit
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
        # chain_to=0,  # Chain back to CH0
        size=2,  # 32-bit transfers
        inc_read=False,
        inc_write=False,
    )

    # We're just transferring the read address back to CH0
    dma_ch1.config(
        read=addressof(buffer_addr_bytes),
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
    # wave = gen_square_wave(BUFFER_SIZE, -16000, 16000)  # Full 16-bit range
    wave = gen_square_wave(BUFFER_SIZE, 0, 256)

    print("Playing wave...")

    sm.active(1)
    setup_dma(addressof(wave))
    dma_ch0.active(1)

    print("Playing tone...")
    play_tone(440, 1, wave)

    print("Playing tone...")
    play_tone(220, 1, wave)

    print("Playing tone...")
    play_tone(880, 1, wave)

    print("Playing tone...")
    play_tone(1600, 1, wave)


    while True:
        time.sleep(1)  # Keep the program running


except KeyboardInterrupt:
    sm.active(0)