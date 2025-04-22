import rp2
from machine import Pin, mem32
from rp2 import PIO, asm_pio, StateMachine
from dump_object import dump_object
from scaler.const import PIO1_BASE, PIO1_SM0_SHIFTCTRL, PIO1_SM0_EXECCTRL
from scaler.status_leds import get_status_led_obj


def read_palette_init(pin_jmp:Pin):
    leds = get_status_led_obj()

    sm_freq = 120_000_000
    pin_led1 = leds.pin_led1

    # PIO1 / SM0 = ID #4
    read_palette_sm = StateMachine(4)
    read_palette_sm.init(
        read_palette,
        freq=sm_freq,
        jmp_pin=pin_jmp,
        sideset_base=pin_led1,
    )

    ctrl_addr = PIO1_SM0_EXECCTRL
    current = mem32[ctrl_addr]

    # Clear the 6 STATUS_N bits (bits 0-5) while preserving all other bits
    # mask = 0xFFFFFFC0  # Mask to clear bits 0-5 (check status of TX FIFO)
    # cleared = current & mask
    #
    # # Set the new STATUS_N value (0b000001) while preserving other bits
    # new_status_n = 0b000001  # STATUS_N value (when TX FIFO is less than 1)
    # new_value = cleared | new_status_n
    #
    # mem32[ctrl_addr] = new_value

    return read_palette_sm

""" This PIO program supports the DMA hardware scaler, by translating color indices from the source image
into palette addresses that are then read in order to send their contents to the display as RGB565 colors. """
@asm_pio(
    in_shiftdir=PIO.SHIFT_RIGHT,
    out_shiftdir=PIO.SHIFT_LEFT,
    sideset_init=(PIO.OUT_LOW,PIO.OUT_LOW,PIO.OUT_LOW,PIO.OUT_LOW),
    # set_init=PIO.OUT_LOW,
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
    label("start")
    nop()              # .side(1)

    pull()                       # First word in is the palette base address
    out(isr, 32)                  # Keep it in the ISR for later - Line # 10

    # START WORD LOOP ----------------------------------------------
    label("new_pull")
    pull()                    #  .side(0b0010)   # line 12
    nop()

    # Check whether the OSR is our NULL trigger to stop (0xFFFFFFFF)
    mov(y, invert(osr))
    jmp(not_y, "end")    # -> Will jump on 0x00000000; since we used invert(), that's our trigger

    # START PIXEL LOOP ----------------------------------------------
    label("pixel_loop")
    nop()                      # .side(0)
    """ Index lookup logic (reverse addition) """
    mov(x, invert(isr))          # Line # 15: ISR has the palette addr, save it in x as the first term in the addition (inverted)

    out(y, 4)                    # shift in 4 bits from OSR (a color index), take that number and use it as a loop counter
    jmp("test_inc1")             # Line # 17

    # START SUBSTRACTION LOOP ---------------------------------------
    label("x++")                 # this loop is equivalent to the following code:
                                 # while (y-- > 0):
                                 #   x++
                                 # leading eventually to x+y (palette + color idx) -> address of this pixel's color
    jmp(x_dec, "test_inc1")      # x-- (this works as x++, since we inverted x).

    label("test_inc1")           # This has the effect of subtracting y from x, eventually.
    jmp(x_dec, "test_inc2")      # We double the substraction because each color is 2 bytes, so every loop we are doing x = x+2

    label("test_inc2")           # test_inc1 and test_inc2 are placeholder labels, the jmp conditions do nothing
    jmp(y_dec, "x++")            # Keep adding

    # Before overwriting the ISR (which contains the palette addr), save it in the Y reg,
    # which we are not using right now
    mov(y, isr)
    mov(isr, invert(x))                     # The final result has to be 1s complement inverted

    push()                       # .side(0)          # 4 bytes pushed from ISR to RX FIFO (1 32bit address = 1px)

    mov(isr, y)                             # restore the ISR with the palette addr, Y is free again
    jmp(not_osre, "pixel_loop")             # Still more nibbles to shift out of the OSR

    # END 1 WORD LOOP ----------------------------------------

    jmp("new_pull")

    label("end")
    nop()              # .side(0b1000)

    irq(block, 0)

    label("park")
    jmp(pin, "start") # last line is always line 31, and the rest are counted backwards

    # end of program will automatically jump to start, since there is no wrap_target
