from rp2 import PIO, asm_pio

""" These are the PIO programs that support the DMA hardware scaler. """
@asm_pio(
    in_shiftdir=PIO.SHIFT_RIGHT,
    out_shiftdir=PIO.SHIFT_LEFT,
    autopull=True,
    pull_thresh=5     # n < 5 might be usable for 50% horizontal downscaling, 0 and n > 5 seems to do upscaling
    # pull_thresh=16, # interesting things happen at weird levels
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

    wrap_target()

    # pull() # An extra pull could be used for horiz downscaling, since it discards pixels

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

    push()  # 4 bytes pushed

    mov(isr, y)  # restore the ISR with the base addr
    irq(4)  # Signal to row_start that pixel is done

@asm_pio(
    set_init=PIO.OUT_LOW,
    sideset_init=PIO.OUT_LOW
)
def row_start():
    # Initialize

    nop()                   .side(0x1) [4]
    pull()                               [1]            # Get initial base address
    nop()                   .side(0x0)

    mov(x, invert(osr))      .side(0x1)[4]                   # Store ~base_addr in X
    pull()                   [1]                          # Get initial row size
    mov(y, osr)               .side(0x0)              # Store row size in Y

    wrap_target()

    # Get pattern and test
    nop()               .side(0x1)[4]
    pull()                  [1]             # Get pattern value
    mov(isr, y)              .side(0x0)        # Save row size in ISR
    mov(y, osr)                     # Get pattern into Y for testing
    jmp(not_y, "skip_add")   [0]       # Skip if pattern = 0

    # Add row size to address
    mov(y, isr)             [0] # Get row size back into Y
    label("add_loop")
    jmp(x_dec, "test")      [0]# Decrement inverted address
    label("test")

    jmp(y_dec, "add_loop")  [4] # Loop while row size > 0

    label("skip_add")
    mov(y, isr)             [0] # restore row size to Y

    # Output current address (this order fixes extra pixels on first row)
    mov(isr, invert(x))  # Get true address

    set(pins, 0x1)          [2]
    push()                  [2]
    set(pins, 0x0)

