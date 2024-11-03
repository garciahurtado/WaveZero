from rp2 import PIO, asm_pio

""" These are the PIO programs that support the DMA hardware scaler. """
@asm_pio(
    in_shiftdir=PIO.SHIFT_RIGHT,
    out_shiftdir=PIO.SHIFT_LEFT,
    autopull=True,
    pull_thresh=5 # n < 5 can be used for horizontal downscaling, 0 seems to do upscaling
    # pull_thresh=16, # interesting things happen with weird levels
)
def read_palette():
    """
    This SM does two things:
    1.Demultiplex bytes
    Takes a full 4 byte word from a 16bit indexed image, and splits it into its individual pixels (so 8 total)

    2. Palette Lookup.
    Uses the 4 bit pixel indices to generate the address which points to the specified color in the palette
    """
    # irq(rel(0))

    out(isr, 32)            # First word is the palette base address
                            # Keep it in the ISR for later

    wrap_target()
    # wait(1, irq, rel(0))

    # pull() # An extra pull could be used for horiz downscaling, since it discards pixels
    wait(0, irq, 6)    # Wait until row addr is ready

    # PIXEL PROCESSING ----------------------------------------------------
    out(y, 4)               # pull 4 bits from OSR

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

    push()  # 4 bytes pushed (pixel 1)
    # irq(rel(0))  # Signal to row_start that pixel is done

    mov(isr, y)  # restore the ISR with the base addr


@asm_pio()
def row_start():
    """
    Generates the next row start address by remembering the first pixel address and
    progressively adding one row worth of pixels to it every loop.

    Uses one's complement addition through substraction:
    https://github.com/raspberrypi/pico-examples/blob/master/pio/addition/addition.pio
    """
    pull()
    mov(x, invert(osr))  # Before doing the addition, store the first number (base address) as its 1s complement
    irq(6, 1)

    wrap_target()

    pull()                  [2]    # Pull the size of the next row

    mov(y, osr)
    jmp(not_y, "skip")     # When row size=0, resend the address of the previous row start

    jmp("test")             [2]
                                    # this loop is equivalent to the following C code:
    label("incr")                   # while (y--)
    jmp(x_dec, "test")      [2]     # x--

    label("test")                   # This has the effect of subtracting y from x, eventually.
    jmp(y_dec, "incr")      [2]

    # Wait for pixel pipeline to clear before changing row address
    # wait(0, irq, 6)

    mov(isr, invert(x))     [2]     # The final result has to be 1s complement inverted

    irq(6, 0)
    push()

    # wait(1, irq, rel(0))

    wrap()

    label("skip")           # When row size=0, resend the address of the previous row start without modifying it, and
    mov(isr, invert(x))   # restart the loop
    # irq(rel(0))
    # wait(1, irq, rel(0))

    push() # push what was already in the ISR
