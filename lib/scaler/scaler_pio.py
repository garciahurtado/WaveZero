import rp2
from machine import Pin, mem32
from rp2 import PIO, asm_pio, StateMachine
from dump_object import dump_object
from scaler.const import PIO1_BASE, PIO1_SM0_SHIFTCTRL, PIO1_SM0_EXECCTRL

def read_palette_init(pin_led1):

    sm_freq = 24_000_000

    # PIO1 / SM0 = ID #4
    read_palette_sm = StateMachine(4)
    read_palette_sm.init(
        read_palette,
        freq=sm_freq,
    )

    ctrl_addr = PIO1_SM0_EXECCTRL
    current = mem32[ctrl_addr]

    # Clear the 6 STATUS_N bits (bits 0-5) while preserving all other bits
    mask = 0xFFFFFFC0  # Mask to clear bits 0-5 (check status of TX FIFO)
    cleared = current & mask

    # Set the new STATUS_N value (0b000001) while preserving other bits
    new_status_n = 0b000001  # STATUS_N value (less than 1)
    new_value = cleared | new_status_n

    mem32[ctrl_addr] = new_value

    return read_palette_sm

""" These are the PIO programs that support the DMA hardware scaler. """
@asm_pio(
    in_shiftdir=PIO.SHIFT_RIGHT,
    out_shiftdir=PIO.SHIFT_LEFT,
    # out_init=(PIO.OUT_LOW,PIO.OUT_LOW,PIO.OUT_LOW,PIO.OUT_LOW),
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
    label("new_sprite")
    # wait(1,irq,0)


    pull()                               [2] #.side(0)   # First word in is the palette base address
    out(isr, 32)                             #.side(0)   # Keep it in the ISR for later


    # set(pins, 0b0001)  # We have 8 pixels per word (outer loop must run twice to total 16 px, THEN pull, since the
    # check is post-decrement, the value ends up being 1 if we want it to run twice )

    # START WORD LOOP ----------------------------------------------
    label("new_pull")
    nop()[15]
    pull()

    # START PIXEL LOOP ----------------------------------------------
    label("wrap_target")
    wrap_target()

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

    jmp(not_osre, "wrap_target")

    # END PIXEL LOOP ----------------------------------------

    # if TX fifo empty, we will jump to start, to grab a new palette addr

    # -- Check if FIFO empty
    mov(y, status)                   # status will be all 1s when FIFO TX level = 0 (n < 1), and 0s otherwise
    jmp(invert(not_y), "new_pull")   # Its NOT empty, which means we can do another pull, lets jump

    irq(0)                           # If we didnt jump, it is empty, so mark the end of the whole SM operation for one sprite

    jmp("new_sprite")

