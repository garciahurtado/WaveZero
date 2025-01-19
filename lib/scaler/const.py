from machine import mem32

"""
Part of the scaler.sprite_scaler package.
Constants for memory access of DMA, PIO and INTERP registers
"""
""" DMA """

CH0_DBG_TCR = 0x804
DMA_BASE = 0x50000000
DMA_BASE_1 = 0x50000040
DMA_BASE_2 = 0x50000080
DMA_BASE_3 = 0x500000C0
DMA_BASE_4 = 0x50000100
DMA_BASE_5 = 0x50000140
DMA_BASE_6 = 0x50000180
DMA_BASE_7 = 0x500001C0
DMA_BASE_8 = 0x50000200
DMA_BASE_9 = 0x50000240
DMA_BASE_10 = 0x50000280

DMA_SIZE_16 = 2
DMA_READ_ADDR = 0x000
DMA_CTRL_AL1 = 0x010
DMA_CTRL_AL2 = 0x020
DMA_CTRL_AL3 = 0x030
DMA_WRITE_ADDR = 0x004
DMA_TRANS_COUNT = 0x008
DMA_WRITE_ADDR_AL1 = 0x018
DMA_READ_ADDR_AL1 = 0x014
DMA_READ_ADDR_AL2 = 0x014
DMA_READ_ADDR_AL3 = 0x014
DMA_TRANS_COUNT_TRIG = 0x01c
DMA_READ_ADDR_TRIG = 0x03C
DMA_WRITE_ADDR_TRIG = 0x02C
DMA_CTRL_TRIG = 0x00c
DMA_AL1_CTRL = 0x010
DMA_DBG_TCR = 0x804

DMA_PX_READ_BASE = DMA_BASE_5
DMA_PX_WRITE_BASE = DMA_BASE_6
DMA_HORIZ_SCALE_BASE = DMA_BASE_7
DMA_ADDR_SKIP = DMA_BASE_8
DMA_SKIP_CTRL = DMA_BASE_9

# SNIFF_CTRL = 0x50000438  # DMA_SNIFF_CTRL register address
# SNIFF_CHAN = 0x50000434  # DMA_SNIFF_CHAN register address
# SNIFF_DATA = 0x50000440  # DMA_SNIFF_DATA register address

# DMA sniffing registers
SNIFF_CTRL = 0x50000434
SNIFF_DATA = 0x50000438
SNIFF_CHAN = 0x50000428
IRQ0_INTE = 0x50000430  # DMA_IRQ0_INTE register address

DMA_FRAC_TIMER = DMA_BASE + 0x420
DMA_TIMER0 = 0x3b

""" PIO """

PIO0_BASE = 0x50200000
PIO1_BASE = 0x50300000

PIO1_TX0 = PIO1_BASE + 0x010
PIO1_RX0 = PIO1_BASE + 0x020

PIO1_TX1 = PIO1_BASE + 0x014
PIO1_RX1 = PIO1_BASE + 0x024

PIO1_TX2 = PIO1_BASE + 0x018
PIO1_RX2 = PIO1_BASE + 0x028

FDEBUG = PIO1_BASE + 0x008
FLEVEL = PIO1_BASE + 0x00c

""" IRQs """
PIO0_IRQ = PIO0_BASE + 0x128
PIO1_IRQ = PIO1_BASE + 0x128


""" DREQ signals """
DREQ_PIO1_TX0 = 8
DREQ_PIO1_RX0 = 12

DREQ_PIO1_TX1 = 9
DREQ_PIO1_RX1 = 13

DREQ_PIO1_TX2 = 10
DREQ_PIO1_RX2 = 14

DREQ_TIMER_0 = 0x3B
DREQ_TIMER_1 = 0x3C

TIMER0_OFFSET = 0x00000420
TIMER0_BITS = 0x00000000

TIMER1_OFFSET = 0x00000424
""" Bytes 0-1 are the numerator, and 2-3 the denominator of a fractional timer with respect to the CPU clock.
So in this case, its 0001/000F or 1/16 of the CPU freq (or 16 times slower) """
TIMER1_BITS = 0x00010002

mem32[DMA_BASE + TIMER1_OFFSET] = TIMER1_BITS

""" Pacing Timer Dividend bits
[31:16] Specifies the X value for the (X/Y) fractional timer.
[15:0] Pacing Timer Divisor. Specifies the Y value for the (X/Y) fractional timer. """

PIO_FSTAT = 0x004
PIO_FDEBUG = 0x008
SM0_INST_DEBUG = 0x0d8
SM1_INST_DEBUG = 0x0f0
SM2_INST_DEBUG = 0x108

SM0_ADDR = 0x0d4
SM1_ADDR = 0x0ec
SM2_ADDR = 0x104

""" INTERP """
SIO_BASE = 0xD0000000
INTERP0_ACCUM0 = SIO_BASE + 0x080
INTERP0_ACCUM1 = SIO_BASE + 0x084
INTERP0_ACCUM0_ADD = SIO_BASE + 0x0b4
INTERP0_ACCUM1_ADD = SIO_BASE + 0x0b8
INTERP0_BASE0 = SIO_BASE + 0x088
INTERP0_BASE1 = SIO_BASE + 0x08C
INTERP0_BASE2 = SIO_BASE + 0x090
INTERP0_CTRL_LANE0 = SIO_BASE + 0x0AC
INTERP0_CTRL_LANE1 = SIO_BASE + 0x0B0
INTERP0_POP_LANE0 = SIO_BASE + 0x094
INTERP0_POP_LANE1 = SIO_BASE + 0x098
INTERP0_POP_FULL = SIO_BASE + 0x09c  # This is what we want for texture lookup
INTERP0_PEEK_LANE0 = SIO_BASE + 0x0a0
INTERP0_PEEK_LANE1 = SIO_BASE + 0x0a4
INTERP0_PEEK_FULL = SIO_BASE + 0x0a8

INTERP1_ACCUM0 = SIO_BASE + 0x0C0
INTERP1_ACCUM1 = SIO_BASE + 0x0C4
INTERP1_ACCUM0_ADD = SIO_BASE + 0x0f4
INTERP1_ACCUM1_ADD = SIO_BASE + 0x0f8
INTERP1_BASE0 = SIO_BASE + 0x0C8
INTERP1_BASE1 = SIO_BASE + 0x0CC
INTERP1_BASE2 = SIO_BASE + 0x0D0
INTERP1_CTRL_LANE0 = SIO_BASE + 0x0EC
INTERP1_CTRL_LANE1 = SIO_BASE + 0x0F0
INTERP1_POP_LANE0 = SIO_BASE + 0x0d4
INTERP1_POP_LANE1 = SIO_BASE + 0x0d8
INTERP1_POP_FULL = SIO_BASE + 0x0DC

INTERP0_BASE_1AND0 = SIO_BASE + 0x0BC
