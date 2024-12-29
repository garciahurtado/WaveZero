from rp2 import PIO, asm_pio
from scaler.dma_scaler_const import DMA_PX_WRITE_BASE

""" These are the PIO programs that support the DMA hardware scaler. """
@asm_pio(
    in_shiftdir=PIO.SHIFT_RIGHT,
    out_shiftdir=PIO.SHIFT_LEFT,
    autopull=True,
    pull_thresh=32,
)
def read_palette():
    """
    This SM does two things:
    1.Demultiplex bytes
    Takes a full 4 byte word from a 16bit indexed image, and splits it into its individual pixels (so 8 total)

    2. Palette Lookup.
    Uses the 4 bit pixel indices to generate the address which points to the specified color in the palette
    """
    out(isr, 32)            # First word is the palette base address
                            # Keep it in the ISR for later

    pull()                  # L:21
    wrap_target()

    # PIXEL PROCESSING ----------------------------------------------------
    out(y, 4)               # L:22 - pull 4 bits from OSR

    """ First off, check for transparent pixels """
    # jmp(not_y, "px_skip")

    """ Index lookup logic (reverse addition) """
    mov(x, invert(isr))             # ISR has the base addr
    jmp("test_inc1")
                                    # this loop is equivalent to the following C code:
    label("incr1")                  # while (y--)
    jmp(x_dec, "test_inc1")         # x--

    label("test_inc1")  # This has the effect of subtracting y from x, eventually.
    jmp(x_dec, "test_inc2")  # We double the substraction because each color is 2 bytes, so we are doing x = x+2
    label("test_inc2")

    jmp(y_dec, "incr1")

    # Before pushing anything at all, save the ISR in the Y reg, which we are not using
    mov(y, isr)
    mov(isr, invert(x))  # The final result has to be 1s complement inverted

    push()  # 4 bytes pushed

    mov(isr, y)  # restore the ISR with the base addr

    # label("px_skip")
    # irq(0, block)

@asm_pio()
def read_addr():
    pull()                  # Get address from TX FIFO
    mov(isr, osr)
    push()                  # Push to RX FIFO

@asm_pio(
    autopush=True,
    push_thresh=32,
    out_shiftdir=PIO.SHIFT_LEFT,
)
def pixel_skip():
    wait(0, irq, 0)              # Wait for IRQ from READ_PALETTE

    mov(osr, null)  # all zeros value
    in_(osr, 32)  # Output to FIFO/DMA

    mov(osr, 0x50000180 + 0x01C)     # Load PX WRITE COUNT TRIG value
    in_(osr, 32)

    mov(osr, 0x50000438)                # Load SNIFF_DATA value
    in_(osr, 32)

    # The sniffer addr should come in here via the TX FIFO
    pull(block)
    out(y, 32)
    in_(y, 31)
    in_(null, 1)        # shift an extra zero, effectively multiplying by 2
    push()

    mov(osr, 0x50300000 + 0x028)        # Load PIO1 SM2 RX FIFO address
    in_(osr, 32)
    irq(0, clear)
