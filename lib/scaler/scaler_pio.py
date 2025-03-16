from machine import Pin
from rp2 import PIO, asm_pio, StateMachine
from dump_object import dump_object

def read_palette_init():
    pin_led1 = Pin(6, Pin.OUT, value=0)
    # pin_led2 = Pin(7, Pin.OUT, value=1)

    """ There's a sweet spot for this frequency, related to the system clock. About 1/3 """
    sm_freq = 24_000_000

    # PIO0 / SM1 = ID #1
    sm_read_palette = StateMachine(
        1, read_palette,
        freq=sm_freq,
        # sideset_base=pin_led1,  # + pin_led2
    )
    return sm_read_palette


""" These are the PIO programs that support the DMA hardware scaler. """
@asm_pio(
    in_shiftdir=PIO.SHIFT_RIGHT,
    out_shiftdir=PIO.SHIFT_LEFT,
    sideset_init=PIO.OUT_LOW, # LED1
    autopull=True,
    pull_thresh=8,
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
    pull()                     # .side(1)
    out(isr, 32)               # .side(0)  # First word is the palette base address
                            # Keep it in the ISR for later
    # irq(noblock, 1)

    # PIXEL PROCESSING LOOP ----------------------------------------------
    wrap_target()
    out(y, 4)              # pull 4 bits from OSR, take that number and use it as a loop counter
    """ Index lookup logic (reverse addition) """
    mov(x, invert(isr))             # ISR has the base addr, save it in x
    jmp("test_inc1")
                                    # this loop is equivalent to the following C code:
    label("incr1")                  # while (y--)
    jmp(x_dec, "test_inc1")         # x--

    label("test_inc1")  # This has the effect of subtracting y from x, eventually.
    jmp(x_dec, "test_inc2")  # We double the substraction because each color is 2 bytes, so every loop we are doing x = x+2
    label("test_inc2")

    jmp(y_dec, "incr1")

    # Before overwriting the ISR, save it in the Y reg, which we are not using right now
    mov(y, isr)
    mov(isr, invert(x))  # The final result has to be 1s complement inverted

    push()             # 4 bytes pushed to RX FIFO

    # END PIXEL LOOP ----------------------------------------

    mov(isr, y)  # restore the ISR with the base addr
                 # Push to RX FIFO






