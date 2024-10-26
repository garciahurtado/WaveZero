import math

import utime

from scaler.dma_scaler_debug import ScalerDebugger
from uctypes import addressof

from machine import Pin
import time
import uctypes

import rp2
from rp2 import DMA, PIO

from profiler import Profiler as prof
from images.indexed_image import Image
from array import array

from scaler.dma_scaler_const import *

class DummyException(Exception):
    def __init__(self):
        pass

dummy_exc = DummyException()

def dma_callback(callback: DMA):
    try:
        raise dummy_exc
    except DummyException as e:
        print(callback.channel, end="")
        print(" DMA CALLBACK !!!")

class DMAScaler:
    h_patterns_ptr = []
    h_pattern_buf_all = []
    max_scale_idx = 8
    scale_index = 0
    last_scale_shift = 0 #
    scale_shift_freq = 20 # every X ms, one pixel shift in scale
    bytes_per_pixel = 2
    sm_indices = None
    sm_row_start = None
    row_tx_count = 0

    debug = False
    debug_buffer_enable = False
    dbg:ScalerDebugger = None

    dma_row_read = None
    read_complete = False

    h_skew = 0

    # channel_names = [
    #     'row_read',
    #     'pixel_read',
    #     'palette',
    #     'pixel_out',
    #     'palette_rst',
    #     'row_size',
    #     'row_start',
    #     'h_scale',
    #     'color_addr',
    # ]

    channel_names = {
        "2": 'row_read',
        "3": 'color_addr',
        "4": 'pixel_out',
        "5": 'h_scale',
        "6": 'row_size',
        "7": 'row_start',
    }
    channels = {}

    h_scale_ptr = None # Ptr to the current scale pattern array
    scale_index_flip = 1

    @rp2.asm_pio(
        in_shiftdir=PIO.SHIFT_LEFT,
    )

    def _pixel_demux():
        """Takes a full 4 byte word from a 16bit indexed image, and splits it into one word for each pixel (so 8 total)"""
        # set(x, null)
        pull()
        set(x, 7)           [0]       # Set up loop counter (8 iterations, 8 pixels per word, 0-7)

        label("loop")

        out(y, 4)           [0]       # pull 4 bits from OSR
        in_(y, 32)          [0]       # spit them out as padded bytes
        push()              [0]

        jmp(x_dec, "loop")  [0]        # Decrement counter and loop if not zero

    @rp2.asm_pio(
        in_shiftdir=PIO.SHIFT_RIGHT,
        out_shiftdir=PIO.SHIFT_LEFT,
        autopull=True,
        # autopush=True,
        # pull_thresh=16, # interesting things happen with weird levels
        pull_thresh=8
        # push_thresh=32,
    )
    def read_palette():
        """
        This SM does two things:
        1.Demultiplex bytes
        Takes a full 4 byte word from a 16bit indexed image, and splits it into its individual pixels (so 8 total)

        2. Palette Lookup.
        Uses the 4 bit pixel indices to generate the address which points to the specified color in the palette
        """
        pull()                           # First word is the palette base address
        mov(isr, osr)            # Keep it in the ISR for later

        wrap_target()
        # pull() # @ This extra pull can be used for horiz 1/2 scale, amusingly

        # PIXEL PROCESSING ----------------------------------------------------
        out(y, 4)              # pull 4 bits from OSR

        """ Index lookup logic (reverse addition) """
        mov(x, invert(isr))         # ISR has the base addr
        jmp("test_inc1")
                                    # this loop is equivalent to the following C code:
        label("incr1")              # while (y--)
        jmp(x_dec, "test_inc1")     # x--
        label("test_inc1")          # This has the effect of subtracting y from x, eventually.
        jmp(x_dec, "test_inc2")     # We double the substraction because each color is 2 bytes, so we are doing x = x+2
        label("test_inc2")

        jmp(y_dec, "incr1")

        # Before pushing anything at all, save the ISR in the Y reg, which we are not using
        mov(y, isr)
        mov(isr, invert(x))         # The final result has to be 1s complement inverted
        push()                      # 4 bytes pushed (pixel 1)
        mov(isr, y)                 # restore the ISR with the base addr

    @rp2.asm_pio()
    def row_start():
        """
        Generates the next row start address by remembering the first pixel address and
        progressively adding one row worth of pixels at a time to it.

        Uses one's complement addition through substraction:
        https://github.com/raspberrypi/pico-examples/blob/master/pio/addition/addition.pio
        """
        pull()
        mov(x, invert(osr))                 # Before doing the math, store the first number as its 1s complement

        wrap_target()

        pull()
        mov(y, osr)

        jmp("test")         [4]
                                            # this loop is equivalent to the following C code:
        label("incr")                       # while (y--)
        jmp(x_dec, "test")  [4]                #     x--

        label("test")                       # This has the effect of subtracting y from x, eventually.
        jmp(y_dec, "incr")  [4]

        mov(isr, invert(x)) [4]             # The final result has to be 1s complement inverted
        push()

    dma_pixel_read = None
    dma_palette = None
    dma_pixel_out = None
    all_h_patterns = []

    def init_pio(self):
        # Set up the PIO state machines
        # freq = 125 * 1000 * 1000
        freq = 8 * 1000 * 1000
        # freq = 100 * 1000

        """ SM0: Pixel demuxer / palette reader """
        sm_indices = self.sm_indices
        sm_indices.init(
            self.read_palette,
            freq=freq,
        )

        """ SM1:  Row start address generator State Machine """
        sm_row_start = self.sm_row_start
        sm_row_start.init(
            self.row_start,
            freq=freq,
            sideset_base=Pin(22), # off board LED
        )
        # sm_row_start.irq(self.sm_irq_handler)

        self.sm_indices.active(1)
        self.sm_row_start.active(1)

    def sm_irq_handler(self, irq):
        print("*** SM IRQ ASSERTED ***")
        print(irq)

    def __init__(self, display, palette_size,
                 channel2, channel3, channel4, channel5, channel6, channel7):
        self.write_addr_base = display.write_addr

        """ DMA Channels"""
        self.dma_row_read = channel2
        self.dma_color_addr = channel3
        self.dma_pixel_out = channel4
        self.dma_h_scale = channel5
        self.dma_row_size = channel6
        self.dma_row_start = channel7

        self.channels = {
            "2" : self.dma_row_read,
            "3": self.dma_color_addr,
            "4" : self.dma_pixel_out,
            "5": self.dma_h_scale,
            "6" : self.dma_row_size,
            "7" : self.dma_row_start,
        }

        """ Init static data buffers for the DMA channels """

        row_size_buff = bytearray(4)
        self.row_size = array("L", row_size_buff)
        # self.row_size[0] = display.width * 2
        self.row_size[0] = 0x000000C0

        print("~ CONTENTS OF ROW_SIZE ARRAY ~")
        print(f"0x{self.row_size[0]:08x}")

        print(f"SETTING ROW_SIZE TO {display.width * 2} =  {self.row_size[0]}")

        self.display = display
        self.write_start_addr = addressof(self.display.write_framebuf)

        self.screen_width = self.display.width
        self.screen_height = self.display.height
        self.palette_size = palette_size

        self.read_complete = False

        """ SM0: Pixel demuxer / index reader """
        self.sm_indices = rp2.StateMachine(4)       # 1st SM in PIO1

        """ SM1:  Row start address generator State Machine """
        self.sm_row_start = rp2.StateMachine(5) # 2nd SM in PIO1

        """ Debug Buffer """
        if self.debug:
            self.dbg = ScalerDebugger(self.sm_indices, self.sm_row_start)
            self.dbg.channel_names = self.channel_names
            self.dbg.channels = self.channels
            self.debug_bytes = self.dbg.get_debug_bytes()

        """ 
        Scaling Patterns ---------------------------------- 
        These buffers will be used to double horizontal pixels at set intervals, in order to implement upscaling 
        The data will be sent to the pixel_out DMA count field. from another channel with a ring buffer of 
        size = len(pattern)
        """
        h_patterns_int = [
            [1, 1, 1, 1, 1, 1, 1, 1],
            [1, 1, 1, 1, 2, 1, 1, 1],                                  # 12.5
            [1, 1, 2, 1, 1, 1, 2, 1],                                           # 25
            [1, 1, 2, 1, 1, 2, 1, 2],                            # 37.5
            [1, 2, 1, 2, 1, 2, 1, 2],                                                 # 50
            [2, 1, 2, 2, 1, 2, 1, 2],       # 62.5
            [2, 1, 2, 2, 2, 1, 2, 2],                                           # 75
            [2, 2, 2, 2, 1, 2, 2, 2],                             # 87.5
            [2, 2, 2, 2, 2, 2, 2, 2]                                # 100
        ]
        """ We need to turn these lists into basic arrays so that the pointers are easier to pass to DMA """
        self.h_patterns_ptr = array('L', [0x00000000] * 9)
        all_patterns = self.all_h_patterns

        print("//// SCALING PATTERNS \\\\\\\\")
        for i, scale_pattern in enumerate(h_patterns_int):
            h_pattern_buf = bytearray(len(scale_pattern) * 4)
            h_pattern = array('L', h_pattern_buf)

            for j, value in enumerate(scale_pattern):
                h_pattern[j] = int(value)

            self.h_patterns_ptr[i] = addressof(h_pattern)
            all_patterns.append(h_pattern)
            self.h_pattern_buf_all.append(h_pattern_buf)


        self.h_patterns = h_patterns_int                # list of actual bitlike patterns (as array)
        # self.h_scale_ptr = self.h_patterns_ptr[self.scale_index]   # current scale / pointer out of the list of pointers
        self.h_scale_ptr = self.h_patterns_ptr[self.scale_index]

        print(f"CURRENT H PATTERN ADDR: 0x{self.h_scale_ptr:08x}")

        """ ---------------------- COLORS -------------------------"""
        num_colors = 8

        """ Create the buffer containing the actual 16 bit colors"""
        palette_buffer = array("B", [0x00] * num_colors * 2)
        base_colors = [0x0000, 0xFF3A, 0xF055, 0x0FF0, 0x00FF, 0xF0A0, 0xA0A0, 0x0FFF]

        for i in range(num_colors):
            color = base_colors[i]
            palette_buffer[i] = color

        self.palette_buffer = palette_buffer
        self.write_start_addr = addressof(display.write_framebuf)

        self.init_pio()
        print(f"Screen dimensions: {self.screen_width}x{self.screen_height}")

        self.init_dma()

    def reset(self):
        self.dma_pixel_out.count = 1
        self.write_start_addr = addressof(self.display.write_framebuf)

        self.sm_indices.restart()
        self.sm_row_start.restart()


    def dma_handler_debug(self, irq):
        print("  >>>> DMA TRANSFER <<<< complete for: #", end='')
        print(irq.channel)

    def pio_handler(self, event):
        """ Handle an IRQ from a SM"""
        print()
        print("+++ A PIO IRQ OCCURRED ++++")
        print()

    def init_dma(self):
        """ Configure and initialize the DMA channels general settings (once only) """

        """ Image Read DMA channel - CH #2 - (feeds SM0) --------------------------------------- """
        dma_row_read_ctrl = self.dma_row_read.pack_ctrl(
            size=0,
            inc_read=True,
            inc_write=False,
            treq_sel= DREQ_PIO1_TX0,
            chain_to=self.dma_row_start.channel,
            bswap=True,
        )
        self.dma_row_read.config(
            count=0,            # To be set later: img pixels per row // 2
            read=0,             # To be set later: memory address of the first pixel of the byte buffer of the sprite
            write=PIO1_TX0,
            ctrl=dma_row_read_ctrl,
            # trigger=True
        )

        """ Color address - CH #3- pass the resulting palette address to the pixel writer """


        dma_color_addr_ctrl = self.dma_color_addr.pack_ctrl(
            size=2,
            inc_read=False,
            inc_write=False,
            treq_sel=DREQ_PIO1_RX0,
            chain_to=self.dma_pixel_out.channel,
            # bswap=True
        )

        self.dma_color_addr.config(
            count=1,
            read=PIO1_RX0,
            write=DMA_BASE_4 + DMA_READ_ADDR_AL1,
            ctrl=dma_color_addr_ctrl,
            # trigger=True
        )

        """ Pixel out DMA channel - CH #4 --------------------- """
        dma_pixel_out_ctrl = self.dma_pixel_out.pack_ctrl(
            size=1,                 # output one pixel at a time (2 bytes)
            inc_read=False,
            inc_write=True,
            chain_to=self.dma_h_scale.channel,
        )

        self.dma_pixel_out.config(
            count=1,            # Increasing this will stretch pixels horizontally for sprite scaling
            read=0,
            write=0,            # To be set later
            ctrl=dma_pixel_out_ctrl,
        )

        """ Horizontal Upscale channel - CH #5 - uses a ring buffer t provide a pattern of pixel repetition for scaling """

        scale_write = DMA_BASE_4 + DMA_TRANS_COUNT
        scale_inc_write = False

        dma_h_scale_ctrl = self.dma_h_scale.pack_ctrl(
            size=2,
            inc_read=True,
            inc_write=scale_inc_write,
            chain_to=self.dma_color_addr.channel,
            ring_sel=0,
            ring_size=4,
        )

        self.dma_h_scale.config(
            count=1,
            read=self.h_scale_ptr,
            write=scale_write,
            ctrl=dma_h_scale_ctrl,
        )


        """ Row Size DMA channel - CH #6 - Sends the new row size to calculate another offset ------------------- """
        rs_write = PIO1_TX1
        rs_inc_write = False

        dma_row_size_ctrl = self.dma_row_size.pack_ctrl(
            size=2,
            inc_read=False,
            inc_write=rs_inc_write,
            treq_sel=DREQ_PIO1_TX1,
            chain_to=self.dma_row_start.channel,
            irq_quiet=False
        )
        self.dma_row_size.config(
            count=1,
            read=self.row_size,
            write=rs_write,
            ctrl=dma_row_size_ctrl,
        )
        self.dma_row_size.irq(handler=self.img_end_irq_handler)

        """ Row Start DMA channel - CH #7 - Reloads the write reg of pixel_out to the start of the next row  """
        dma_row_start_ctrl = self.dma_row_start.pack_ctrl(
            size=2,
            inc_read=False,
            inc_write=False,
            treq_sel=DREQ_PIO1_RX1,
            chain_to=self.dma_row_read.channel,
        )
        self.dma_row_start.config(
            count=1,
            read=PIO1_RX1,
            write=DMA_BASE_4 + DMA_WRITE_ADDR,
            ctrl=dma_row_start_ctrl,
        )

    def img_end_irq_handler(self, irq_obj):
        if self.debug:
            print()
            print("<<<<<< IMG END IRQ - Triggered / Read Complete >>>>>>")
            print()
            time.sleep_ms(100)
        self.read_complete = True

    def config_dma(self, image, x, y, width, height):
        display = self.display
        num_pixels = width * height
        write_addr_base = self.write_addr_base

        write_addr = display.write_addr
        write_offset = ((y * display.width) + x) * 2  # since the display is 16 bit, we multiply x 2
        write_addr += write_offset
        self.write_addr = write_addr

        if self.debug:
            print(f"WRITE START ADDR: 0x{write_addr_base:08x}")
            print(f"DRAWING AT {x},{y} (size {width}x{height})")
            print(f"READING {num_pixels} PIXELS in {len(image.pixel_bytes)} BYTES FROM ADDR: 0x{addressof(image.pixel_bytes):08x}")

            print("DISPLAY & MEM DETAILS:")
            print("------------------------")
            print(f"\twidth: {display.width}px")
            print(f"\theight: {display.height}px")
            print(f"\tdisplay_out_start: 0x{write_addr_base:08x}")
            print(f"\tsprite_out_addr + offset: 0x{write_addr:08x}")
            print(f"\timg_read_addr: 0x{addressof(image.pixel_bytes):08x}")
            print(f"\tcolor_addr: 0x{addressof(self.palette_buffer):08x}")
            # print(f"\tcolor_addr_ptr: 0x{addressof(self.rst_addr_ptr):08x}")
            print(f"\trow_size: 0x{self.row_size[0]:08x}")


    def show(self, image: Image, x, y, width, height, scale=1):
        """ shift the scale"""

        prof.start_profile('scaler.scale_shift')
        last_scale_shift = self.last_scale_shift
        diff = utime.ticks_diff(utime.ticks_ms(),last_scale_shift)

        if diff > self.scale_shift_freq:
            self.last_scale_shift = utime.ticks_ms()

            self.scale_index += (1 * self.scale_index_flip)

            if self.scale_index > self.max_scale_idx:
                self.scale_index = self.max_scale_idx
                self.scale_index_flip = self.scale_index_flip * -1

            if self.scale_index < 0:
                self.scale_index = 0
                self.scale_index_flip = self.scale_index_flip * -1

        x = x - (self.scale_index * 2)

        prof.end_profile('scaler.scale_shift')

        """ ----------- Set variable per-image configuration on all the DMA channels -------------- """

        prof.start_profile('scaler.prep_img_vars')
        num_pixels = int(width * height)
        # row_tx_count = int(width + self.h_skew) # Adding / substracting can apply skew to the image
        row_tx_count = round(width / 2)

        write_offset = ((y * self.display.width) + x) * 2 # since the display is 16 bit, we multiply x 2
        self.write_addr = self.write_start_addr + write_offset
        prof.end_profile('scaler.prep_img_vars')

        if self.debug:
            print(f"IMAGE WIDTH (px): {width}")
            print(f"TOTAL IMG PX: {num_pixels}")
            print(f"ROW TX COUNT (32bit): {row_tx_count}")
        self.row_tx_count = row_tx_count

        prof.start_profile('scaler.config_dma')
        self.config_dma(image, x, y, width, height)
        prof.end_profile('scaler.config_dma')

        # print(f"SCALER WRITING TO WRITE BUFF @:{self.write_addr_base:08x}")

        prof.start_profile('scaler.dma_init_values')
        self.dma_row_read.read = image.pixel_bytes_addr                 # CH2
        self.dma_row_read.count = row_tx_count                          #   for 1byte width
        self.dma_pixel_out.read = self.palette_buffer                   # CH5
        self.dma_pixel_out.write = self.write_addr
        self.dma_pixel_out.count = 1                                    # We can set the horizontal scale here (upscaling)
        self.dma_h_scale.read = self.h_patterns_ptr[self.scale_index]   # CH5 -

        self.dma_row_size.count = image.height                          # CH6
        self.dma_row_start.count = 1                                    # CH7 -
        prof.end_profile('scaler.dma_init_values')

        if self.debug:
            for idx in self.channel_names.keys():
                self.dbg.debug_dma_channel(idx, 'BEFORE_START')

        self.read_complete = False

        """ State Machine startup -----------------------"""
        prof.start_profile('scaler.start_pio')
        self.sm_indices.restart()
        self.sm_row_start.restart()

        """ Prime with first palette addr. """
        color_addr = addressof(image.palette_bytes)
        if self.debug:
            print(f"~~~ Priming SM0 with {color_addr:08x} ~~~")

        self.sm_indices.put(color_addr)

        """ Prime SM with first framebuffer addr. """
        self.sm_row_start.put(self.write_addr)

        self.sm_indices.active(1)
        self.sm_row_start.active(1)

        prof.end_profile('scaler.start_pio')

        """ DMA - We only need to kick off the channels that don't have any other means to get started (like chain_to)"""
        prof.start_profile('scaler.start_dma')
        self.dma_color_addr.active(1)
        self.dma_row_read.active(1)
        self.dma_row_size.active(1)
        # self.dma_row_start.active(1)
        # self.dma_h_scale.active(1)

        prof.end_profile('scaler.start_dma')

        if self.debug:
            self.dbg.debug_fifos()

        prof.start_profile('scaler.inner_loop')
        """ As far as DMA goes, active and busy are the same thing (i think)"""
        while (not self.read_complete):

            if self.debug:
                for idx in self.channel_names.keys():
                    self.dbg.debug_dma_channel(idx, 'IN_LOOP')

            if self.debug_buffer_enable:
                print("----------------------------------------------")
                print("DEBUG BUFFER:")
                self.dbg.debug_buffer(self.debug_bytes)

        prof.end_profile('scaler.inner_loop')

        if self.debug:
            print("<<<-------- FINISHED READING IMAGE ---------->>>")

            for idx in self.channel_names.keys():
                self.dbg.debug_dma_channel(idx, 'POST_DMA')

        # return False # debug
        self.stop_scaler()
        # self.update_scale()

    def stop_scaler(self):
        self.dma_row_read.active(0)
        self.dma_color_addr.active(0)
        self.dma_pixel_out.active(0)
        self.dma_h_scale.active(0)
        self.dma_row_start.active(0)
        self.dma_row_size.active(0)
        self.read_complete = False

        self.sm_indices.restart()
        self.sm_row_start.restart()

    def update_scale(self):
        max_idx = len(self.h_patterns_ptr) - 1

        if self.scale_index_flip > 0:
            self.scale_index += 1
            if self.scale_index > max_idx:
                self.scale_index = max_idx
                self.scale_index_flip *= -1
        else:
            self.scale_index -= 1
            if self.scale_index <= 0:
                self.scale_index = 0
                self.scale_index_flip *= -1

    def __del__(self):
        # Clean up DMA channels
        self.dma_row_read.close()
        self.dma_color_addr.close()
        self.dma_pixel_out.close()
        self.dma_h_scale.close()
        self.dma_row_start.close()
        self.dma_row_size.close()
