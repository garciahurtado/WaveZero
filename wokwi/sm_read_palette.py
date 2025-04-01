from rp2 import asm_pio, PIO
@asm_pio(
    in_shiftdir=PIO.SHIFT_RIGHT,
    out_shiftdir=PIO.SHIFT_LEFT,
    sideset_init=(PIO.OUT_LOW,PIO.OUT_LOW,PIO.OUT_LOW,PIO.OUT_LOW),
    # set_init=(PIO.OUT_LOW,PIO.OUT_LOW,PIO.OUT_LOW,PIO.OUT_LOW),
    pull_thresh=32,
)
def read_palette():
    """
    This SM does two things:
    1.Demultiplex bytes
    Takes a full 4 byte word from a 16bit indexed image, and splits it into its individual pixels (so 8 total)

    2. Palette Lookup.
    Uses the 4 bit pixel indices to generate the address which points to the specified color in the palette in RAM
    """
    label("new_addr")
    # set(pins, 0x1)     [15]

    pull()                               [0] #.side(0)   # First word in is the palette base address
    out(isr, 32)                             #.side(0)   # Keep it in the ISR for later

    # set(pins, 0b0001)  # We have 8 pixels per word (outer loop must run twice to total 16 px, THEN pull, since the
    # check is post-decrement, the value ends up being 1 if we want it to run twice )

    # START WORD LOOP ----------------------------------------------
    label("new_pull")
    pull(ifempty)
    # START PIXEL LOOP ----------------------------------------------
    label("wrap_target")
    wrap_target()
    irq(0)
    """ Index lookup logic (reverse addition) """
    mov(x, invert(isr))             # ISR has the palette addr, save it in x

    out(y, 4)                       # pull 4 bits from OSR, take that number and use it as a loop counter (color id)
    jmp("test_inc1")
                                    # this loop is equivalent to the following C code:
    label("incr1")                  # while (y--)
    jmp(x_dec, "test_inc1")         # x--

    label("test_inc1")              # This has the effect of subtracting y from x, eventually.
    jmp(x_dec, "test_inc2")         # We double the substraction because each color is 2 bytes, so every loop we are doing x = x+2
    label("test_inc2")

    jmp(y_dec, "incr1")

    # Before overwriting the ISR (which contains the palette addr), save it in the Y reg,
    # which we are not using right now
    mov(y, isr)
    mov(isr, invert(x))                     # The final result has to be 1s complement inverted

    push()                                  # 4 bytes pushed from ISR to RX FIFO (1 32bit address = 1px)
    mov(isr, y)                             # restore the ISR with the palette addr, Y is free again

    nop()   [0]         .side(3)
    nop()   [0]         .side(0)

    jmp(not_osre, "wrap_target")

    nop()   [0]         .side(3)
    nop()   [0]         .side(0)

    jmp("new_pull")                     # 8x loop finished, pull new pixels (32 bits)
