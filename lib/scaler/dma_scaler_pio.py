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

    pull() # An extra pull could be used for horiz downscaling, since it discards pixels
    wrap_target()

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
    # wait(0, irq, 4)         # wait in case new row is still starting

    mov(isr, y)  # restore the ISR with the base addr

@asm_pio(
)
def row_start():
    # Initialize
    # nop()                   .side(0x1) [0]
    pull()                               [0]            # Get initial base address
    mov(isr, osr)
    push()


    mov(x, invert(osr))    #  .side(0x1)[0]                   # Store ~base_addr in X
    pull()                   [1]                          # Get initial row size
    mov(y, osr)            #   .side(0x0)              # Store row size in Y

    wrap_target()

    # Get pattern and test
    # nop()               .side(0x1)[0]
    # irq(rel(4))

    pull()                  [0]             # Get pattern value
    mov(isr, y)           #   .side(0x0)        # Save row size in ISR
    mov(y, osr)                     # Get pattern into Y for testing
    jmp(not_y, "skip_add")   [8]       # Skip if pattern = 0

    # Add row size to address
    mov(y, isr)             [8] # Get row size back into Y
    label("add_loop")
    jmp(x_dec, "test")      [8]# Decrement inverted address
    label("test")

    jmp(y_dec, "add_loop")  [2] # Loop while row size > 0

    mov(y, isr)             [2] # restore row size to Y

    label("after_loop")
    # Output current address (this order fixes extra pixels on first row)
    mov(isr, invert(x))  # Get true address

    # set(pins, 0x1)          [2]
    push()                    [8]
    # set(pins, 0x0)              # LED DEBUG

    wrap()

    label("skip_add")       # This causes an addtl row addr to be sent when "skip"
    mov(y, isr)[2]  # save row size to Y, for later
    #
    mov(isr, invert(x))
    push()                  [8]

    jmp("after_loop")


@asm_pio()
def _row_counter():
    pull()  # Get total rows
    mov(y, osr)  # Y = row count

    wrap_target()

    wait(1, irq, 4)  # Wait for IRQ 4 from row_start
    irq(clear, 4)  # Clear the flag
    jmp(y_dec, "cont")  # Dec counter, continue if not zero
    irq(0)  # Signal completion on IRQ 0
    label("cont")

