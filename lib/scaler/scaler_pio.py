import rp2
from machine import Pin, mem32
from rp2 import PIO, asm_pio, StateMachine
from dump_object import dump_object
from scaler.const import PIO1_BASE, PIO1_SM0_SHIFTCTRL, PIO1_SM0_EXECCTRL
from scaler.status_leds import get_status_led_obj


def read_palette_init(pin_jmp:Pin):
    leds = get_status_led_obj()

    sm_freq = 92_000_000
    pin_led1 = leds.pin_led1

    # PIO1 / SM0 = ID #4
    read_palette_sm = StateMachine(4)
    read_palette_sm.init(
        read_palette,
        freq=sm_freq,
        jmp_pin=pin_jmp,
        set_base=pin_jmp,
        sideset_base=pin_led1,
    )

    ctrl_addr = PIO1_SM0_EXECCTRL
    current = mem32[ctrl_addr]

    return read_palette_sm

@asm_pio(
    in_shiftdir=PIO.SHIFT_RIGHT,
    out_shiftdir=PIO.SHIFT_LEFT,
    set_init=PIO.OUT_LOW,
    sideset_init=(PIO.OUT_LOW,PIO.OUT_LOW,PIO.OUT_LOW,PIO.OUT_LOW),
    pull_thresh=32,
)
def read_palette():
    """
    This PIO program does two things:
    1.Demultiplex bytes
    Takes a full 4 byte word from a 16bit indexed image, and splits it into its individual pixels (so 8 total)

    2. Palette Lookup.
    Uses the 4 bit pixel indices to generate the address which points to the specified color in the palette in RAM

    These addresses are then sent to DMA to pull the final RGB565 colors from the palette, which are sent to the display
    """
    label("start")
    set(pin, 0)                     # reset the JMP pin
    pull()                          # First word in is the palette base address
    out(isr, 32)                    # Keep it in the ISR for later -

    # START WORD LOOP ----------------------------------------------
    label("new_pull")
    pull()                          #  .side(0b0010)   # line 15

    # Check whether the OSR contains our NULL trigger for end of sprite (0xFFFFFFFF)
    mov(y, invert(osr))
    jmp(not_y, "end")               # -> Will jump on 0x00000000; since we used invert(), that's our trigger

    # START PIXEL LOOP ----------------------------------------------
    label("pixel_loop")

    """ Index lookup logic (reverse addition) """
    mov(x, invert(isr))             # Line # 18: ISR has the palette addr, save it in x as the first term in the addition (inverted)

    out(y, 4)                       # shift in 4 bits from OSR (a color index), take that number and use it as a loop counter
    jmp("test_inc1")                # Line # 20

    # START SUBSTRACTION LOOP ---------------------------------------
    label("x++")                    # this loop is equivalent to the following code:
                                    # while (y-- > 0):
                                    #   x++
                                    # leading eventually to x+y (palette + color idx) -> address of this pixel's color
    jmp(x_dec, "test_inc1")         # x-- (this works as x++, since we inverted x).

    label("test_inc1")              # This has the effect of subtracting y from x, eventually.
    jmp(x_dec, "test_inc2")         # We double the substraction because each color is 2 bytes, so every loop we are doing x = x+2

    label("test_inc2")              # test_inc1 and test_inc2 are placeholder labels, the jmp conditions do nothing
    jmp(y_dec, "x++")               # Keep adding

    # Before overwriting the ISR (which contains the palette addr), save it in the Y reg,
    # which we are not using right now
    mov(y, isr)
    mov(isr, invert(x))             # The final result has to be 1s complement inverted

    push()                          # .side(0)          # 4 bytes pushed from ISR to RX FIFO (1 32bit address = 1px)

    mov(isr, y)                     # restore the ISR with the palette addr, Y is free again
    jmp(not_osre, "pixel_loop")     # Still more nibbles to shift out of the OSR

    # END 1 WORD LOOP ----------------------------------------

    jmp("new_pull")

    label("end")
    irq(block, 0)                   # Signal that we are done, wait until ack
    jmp(pin, "start")               # last line is always number 31, and the rest are counted down from there

    # end of program will automatically jump to start, since there is no wrap_target
