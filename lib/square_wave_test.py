from machine import Pin, PWM
import rp2
import array
import uctypes

# Constants
PWM_PIN = 18  # The pin connected to the PWM output
PWM_FREQ = 8_000_000  # PWM frequency in Hz
BUFFER_SIZE = 1024  # Size of the buffer

# Define DMA base address and channel
DMA_BASE = 0x50000000
DMA_CHANNEL = 0  # Using DMA channel 0

# Initialize the PWM on the specified pin
pwm = PWM(Pin(PWM_PIN))
pwm.freq(PWM_FREQ)

# Create a buffer to hold the PWM duty cycle values
# Fill the buffer with a simple waveform (e.g., a ramp for demonstration)
pwm_buffer = array.array("H", [0] * BUFFER_SIZE)
for i in range(BUFFER_SIZE):
    pwm_buffer[i] = int((i / BUFFER_SIZE) * 65535)  # Fill with a ramp waveform


# Set up a DMA channel
# DMA control block structure

DMA_CTRL = {
    "READ_ADDR": 0x0 | uctypes.UINT32,
    "WRITE_ADDR": 0x4 | uctypes.UINT32,
    "TRANSFER_COUNT": 0x8 | uctypes.UINT32,
    "CTRL_TRIG": 0xC | uctypes.UINT32,
    "AL1_CTRL": 0x10 | uctypes.UINT32,
}
dma = rp2.DMA()
dma_ctrl0 = dma.pack_ctrl(
    size=2,  # 32-bit transfers
    inc_read=True,
    inc_write=False,
    irq_quiet=False,
    bswap=False,
    treq_sel=0x3b,
)
dma.config(
    count=BUFFER_SIZE,
    read=pwm_buffer,
    write=uctypes.addressof(pwm) + 0x10,
    ctrl=dma_ctrl0,
)

# dma.config(
#     read=pwm_buffer,            # Source is our buffer
#     write=pwm,                   # Destination is the PWM duty cycle register
#     length=BUFFER_SIZE,        # Length of the transfer (number of items)
#     transfer_size=rp2.DMA.SIZE_16,  # Transfer size (16 bits for the PWM duty cycle)
#     trigger=pwm,               # Trigger on the PWM (or timer, depending on your needs)
#     repeat=True                # Repeat indefinitely
# )
# Map DMA control block to the actual DMA channel

# Enable the DMA channel
dma.active(1)

# Start PWM
pwm.duty_u16(0)  # Initial duty cycle value

# The DMA now continuously updates the PWM duty cycle based on the buffer contents

# Optional: Adjust the buffer content in real-time for dynamic control
# For example, modify the buffer to generate different waveforms
# (e.g., sine wave, square wave, etc.)

# Cleanup on program exit
# dma.stop()
# pwm.deinit()
