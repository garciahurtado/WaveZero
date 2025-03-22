from machine import Pin
from rp2 import PIO, asm_pio, StateMachine
from dump_object import dump_object

def read_palette_init(pin_jmp):
    pin_led1 = Pin(6, Pin.OUT, value=0)

    """ There's a sweet spot for this frequency, related to the system clock. About 1/3 """
    sm_freq = 24_000_000

    # PIO1 / SM0 = ID #4
    read_palette_sm = StateMachine(4)
    read_palette_sm.init(
        read_palette,
        freq=sm_freq,
        sideset_base=pin_led1,  # + pin_led2
        jmp_pin=pin_jmp
    )
    print("*** THIS also SHOULD ONLY HAPPEN ONCE ***")
    print(asm_pio)

    return read_palette_sm


""" These are the PIO programs that support the DMA hardware scaler. """
@asm_pio(
    in_shiftdir=PIO.SHIFT_RIGHT,
    out_shiftdir=PIO.SHIFT_LEFT,
    sideset_init=PIO.OUT_LOW, # LED1
    # jmp_init=PIO.OUT_LOW,
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

    pull()                       [2].side(1)
    out(isr, 32)                    .side(0)
    # First word in is the palette base address
    # Keep it in the ISR for later

    # PIXEL PROCESSING LOOP ----------------------------------------------
    wrap_target()

    """ Index lookup logic (reverse addition) """
    mov(x, invert(isr))             # ISR has the base addr, save it in x
    jmp(pin, "new_addr")

    out(y, 4)                       # pull 4 bits from OSR, take that number and use it as a loop counter (color id)
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

    push()             # 4 bytes pushed to RX FIFO (2px)

    # END PIXEL LOOP ----------------------------------------

    mov(isr, y)  # restore the ISR with the base addr
                 # Push to RX FIFO

    # When we signal, go get a new palette addr. If not, return to wrap_target
    # jmp(pin, "new_addr")


