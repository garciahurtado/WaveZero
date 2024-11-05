from rp2 import PIO, asm_pio

""" These are the PIO programs that support the DMA hardware scaler. """
@asm_pio(
    in_shiftdir=PIO.SHIFT_RIGHT,
    out_shiftdir=PIO.SHIFT_LEFT,
    autopull=True,
    pull_thresh=5# n < 5 can be used for horizontal downscaling, 0 seems to do upscaling
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

@asm_pio()
def row_start():
    # Initialize
    pull()  # Get initial base address
    mov(x, invert(osr))  # Store ~base_addr in X
    pull()  # Get initial row size
    mov(y, osr)  # Store row size in Y

    wrap_target()
    # Output current address
    mov(isr, invert(x))  # Get true address
    push()  # Push address

    # Get pattern and test
    pull()  # Get pattern value
    mov(isr, y)  # Save row size in ISR
    mov(y, osr)  # Get pattern into Y for testing
    jmp(not_y, "skip_add")  # Skip if pattern = 0

    # Add row size to address
    mov(y, isr)  # Get row size back into Y
    label("add_loop")
    jmp(x_dec, "test")  # Decrement inverted address
    label("test")
    jmp(y_dec, "add_loop")  # Loop while row size > 0

    label("skip_add")
    mov(y, isr)  # restore row size to Y

# @asm_pio(
#     autopull=True,
#     pull_thresh=8
# )
@asm_pio()
def _row_start():
    # Init
    pull()  # Get initial base address
    mov(x, invert(osr))  # ~addr in X
    pull()  # Get row size
    mov(isr, osr)  # Save row size

    wrap_target()
    # Output address
    mov(isr, invert(x))  # Get true address11
    push()
    mov(isr, osr)  # Restore row size

    # Get pattern
    pull()  # Get pattern value
    mov(y, osr)  # Y = pattern
    jmp(not_y, "end")  # If pattern=0, next row

    # Single decrement loop
    mov(y, isr)  # Y = row size
    label("subtract")
    jmp(x_dec, "next")  # Decrement addr
    label("next")
    jmp(y_dec, "subtract")  # Loop while Y>0

    label("end")
    wrap()
