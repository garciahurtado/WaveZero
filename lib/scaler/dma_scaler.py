from scaler.dma_scaler_const import *
from scaler.dma_scaler_debug import ScalerDebugger
from machine import Pin
import time
import uctypes

import rp2
from rp2 import DMA, PIO

from profiler import Profiler as prof
from images.indexed_image import Image
from uctypes import addressof
from array import array
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

    channel_names = [
        'row_read',
        'pixel_read',
        'palette',
        'pixel_out',
        'palette_rst',
        'row_size',
        'row_start',
        'h_scale',
    ]

    h_scale_ptr = None # Ptr to the current scale pattern array
    scale_index_flip = 1

    @rp2.asm_pio(
        in_shiftdir=PIO.SHIFT_LEFT,
    )

    def pixel_demux():
        """Takes a full 4 byte word from a 16bit indexed image, and splits it into one word for each pixel (so 8 total)"""
        # set(x, null)
        pull()
        set(x, 7)           [2]       # Set up loop counter (8 iterations, 8 pixels per word, 0-7)

        label("loop")

        out(y, 4)           [2]       # pull 4 bits from OSR
        in_(y, 32)          [2]       # spit them out as padded bytes
        push()              [2]

        jmp(x_dec, "loop")  [2]        # Decrement counter and loop if not zero

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

        jmp("test")
                                            # this loop is equivalent to the following C code:
        label("incr")                       # while (y--)
        jmp(x_dec, "test")                  #     x--

        label("test")                       # This has the effect of subtracting y from x, eventually.
        jmp(y_dec, "incr")

        mov(isr, invert(x))              # The final result has to be 1s complement inverted
        push()

    dma_pixel_read = None
    dma_palette = None
    dma_pixel_out = None
    all_h_patterns = []

    def init_pio(self):
        # Set up the PIO state machines
        # freq = 125 * 1000 * 1000
        # freq = 62 * 1000 * 1000
        freq = 4 * 1000

        """ SM0: Pixel demuxer / index reader """
        sm_indices = self.sm_indices
        sm_indices.init(
            self.pixel_demux,
            freq=freq,
            # sideset_base=Pin(25),
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

    def __init__(self, display, palette_size, channel2, channel3, channel4, channel5, channel6, channel7, channel8, channel9):
        self.write_addr_base = display.write_addr

        """ Load constants """
        # self.c = const_all()

        """ Init static data buffers for the DMA channels """

        row_size_buff = bytearray(4)
        self.row_size = array("L", row_size_buff)
        # self.row_size[0] = display.width * 2
        self.row_size[0] = 0x000000C0 # @TODO: this should be dynamic based on img width

        print("~ CONTENTS OF ROW_SIZE ARRAY ~")
        print(f"0x{self.row_size[0]:08x}")
        # row_size_bytes = (row_size).to_bytes(4, 'little')
        # row_size_buff = row_size_bytes
        self.row_size_buff = row_size_buff

        print(f"SETTING ROW_SIZE TO {display.width * 2} =  {self.row_size[0]}")

        self.display = display
        self.write_start_addr = addressof(self.display.write_framebuf)

        self.screen_width = self.display.width
        self.screen_height = self.display.height
        self.palette_size = palette_size

        """ DMA Channels"""
        self.dma_row_read = channel2
        self.dma_pixel_read = channel3
        self.dma_palette = channel4
        self.dma_pixel_out = channel5
        self.dma_palette_rst = channel6
        self.dma_row_size = channel7
        self.dma_row_start = channel8
        self.dma_h_scale = channel9
        self.color_addr_list = None

        self.read_complete = False

        """ SM0: Pixel demuxer / index reader """
        self.sm_indices = rp2.StateMachine(4)       # 1st SM in PIO1

        """ SM1:  Row start address generator State Machine """
        self.sm_row_start = rp2.StateMachine(5) # 2nd SM in PIO1

        """ Debug Buffer """
        if self.debug:
            self.dbg = ScalerDebugger(self.sm_indices, self.sm_row_start)
            self.debug_bytes = self.dbg.make_debug_bytes()

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

        h_patterns_ptr = array('L', [1] * 9)
        all_patterns = self.all_h_patterns
        self.scale_index = 0

        print("//// SCALING PATTERNS \\\\\\\\")
        for i, scale_pattern in enumerate(h_patterns_int):
            # tmp = [0] * len(h_patterns_int)
            h_pattern = array('L', [0] * (len(scale_pattern)))
            all_patterns.append(h_pattern)

            for j, value in enumerate(scale_pattern):
                h_pattern[j] = value

            h_patterns_ptr[i] = addressof(h_pattern)

        print("H PATTERN :")
        print(h_patterns_int[self.scale_index])

        self.h_patterns = h_patterns_int                # list of actual bitlike patterns (as array)
        self.h_patterns_ptr = h_patterns_ptr
        self.h_scale_ptr = self.h_patterns_ptr[self.scale_index]   # current scale / pointer out of the list of pointers

        """ ---------------------- COLORS -------------------------"""
        num_colors = 8

        """ Create the buffer containing the actual 16 bit colors"""
        palette_buffer = array("B", [0x00] * num_colors * 2)
        base_colors = [0x0011, 0xFFFF, 0x00FF, 0xFF00, 0x00FF, 0xF0A0, 0xA0A0, 0x0FFF]

        for i in range(num_colors):
            color = base_colors[i]
            palette_buffer[i] = color

        self.palette_buffer = palette_buffer
        self.palette_buffer_addr = addressof(palette_buffer)
        print(f"((( Palette buffer addr: 0x{addressof(palette_buffer):08x} )))")

        """ Now create a buffer containing the addresses of all these colors"""
        self.color_addr_list = array("L", [0x00000000] * num_colors)

        for i in range(len(self.color_addr_list)):
            self.color_addr_list[i] = self.palette_buffer_addr + (i*4)

        """ Palette initial address """
        rst_addr = uctypes.addressof(self.color_addr_list)
        self.rst_addr = rst_addr

        # PTR containing the palette address, so we can pass it indirectly
        rst_addr_ptr = array("L", [0])
        rst_addr_ptr[0] = int(rst_addr)
        self.rst_addr_ptr = rst_addr_ptr

        print(f"Palette ptr: 0x{addressof(rst_addr_ptr):08x}")
        print(f"Palette ptr contains: 0x{rst_addr_ptr[0]:08x}")

        """ ----------- CONFIGURE PALETTE --------------------------"""

        if self.debug:
            # print()
            # print(f"Restore ADDR ARRAY: {restore_addr_arr:08x}")
            # print(f"Restore ADDR ARRAY CONTENTS: {mem32[restore_addr_arr]:08x}")
            # print()

            print(f"PALETTE COLORS ADDRESSES (size {palette_size})")
            print(f"START: {addressof(self.color_addr_list):08x} ")

            # for i in range(palette_size // 4):
            #     addr = uctypes.addressof(self.color_addr_list) + (i * 4)
            #     cont = mem32[addr]
            #     print(f"ADDR: {cont:08x}") #-{value2:02x}-{value3:02x}-{value4:02x}")

            print()

        self.init_pio()
        print(f"Screen dimensions: {self.screen_width}x{self.screen_height}")

        self.ch_names = self.channel_names
        self.channels = [
            self.dma_row_read, self.dma_pixel_read, self.dma_palette,
            self.dma_pixel_out, self.dma_palette_rst, self.dma_row_size,
            self.dma_row_start, self.dma_h_scale]

        if self.debug:
            print(f"CALLING INIT_DMA with color ADDR list @ 0x{uctypes.addressof(self.color_addr_list):08x}")
            # for color_addr in self.color_addr_list:
            #     print(f"- {color_addr:08x}")

        self.init_dma()

    def reset(self):
        self.sm_indices.restart()
        self.sm_row_start.restart()

        self.dma_pixel_read.count = self.row_tx_count
        self.write_start_addr = addressof(self.display.write_framebuf)
        self.h_scale_ptr = self.h_patterns_ptr[self.scale_index]
        self.dma_h_scale.read = self.h_scale_ptr
        self.dma_h_scale.active(0)


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
            size=2,
            inc_read=True,
            inc_write=False,
            treq_sel= DREQ_PIO1_TX0,
            # chain_to=self.dma_row_size.channel,
            bswap=True,
            irq_quiet=False
        )
        self.dma_row_read.config(
            count=0,            # To be set later: img pixels per row // 8
            read=0,             # To be set later: memory address of the first pixel of the byte buffer of the sprite
            write= PIO1_TX0,
            ctrl=dma_row_read_ctrl,
        )
        self.dma_row_read.irq(handler=self.img_end_irq_handler)

        """ Pixel reader DMA channel - CH #3 - (reads from SM0) ---------------------------- """
        dma_pixel_read_ctrl = self.dma_pixel_read.pack_ctrl(
            size=2,
            inc_read=False,
            inc_write=False,
            treq_sel= DREQ_PIO1_RX0,
            chain_to=self.dma_row_size.channel
        )

        self.dma_pixel_read.config(
            count=1,
            read= PIO1_RX0,
            write=DMA_BASE_4 + DMA_TRANS_COUNT_TRIG,
            ctrl=dma_pixel_read_ctrl,
            # trigger=True
        )

        """ Palette DMA channel - CH #4 - --------------------------------------- """
        palette_write = DMA_BASE_5 + DMA_READ_ADDR_AL1
        palette_inc_write = False

        dma_palette_ctrl = self.dma_palette.pack_ctrl(
            size=2,                     # 4 bytes per transfer
            inc_read=True,
            inc_write=palette_inc_write,
            chain_to=self.dma_pixel_out.channel,
            ring_sel=True,
            ring_size=1,

        )
        self.dma_palette.config(
            count=0,
            read=self.color_addr_list,
            write=palette_write,
            ctrl=dma_palette_ctrl,
        )


        """ Pixel out DMA channel - CH #5 --------------------- """
        dma_pixel_out_ctrl = self.dma_pixel_out.pack_ctrl(
            size=1,                 # one pixel at a time (2 bytes)
            inc_read=False,
            inc_write=True,
            chain_to=self.dma_h_scale.channel,
        )

        self.dma_pixel_out.config(
            count=1,            # In the future, this can be used to scale out (stretch) pixels for sprite scaling
            read=0,
            write=0,            # To be set later
            ctrl=dma_pixel_out_ctrl,
        )

        """ palette reset DMA channel - CH #6 - Reconfigures initial palette read addr ------------------- """
        dma_palette_rst_ctrl = self.dma_palette_rst.pack_ctrl(
            size=2,
            inc_read=False,
            inc_write=False,
            chain_to=self.dma_pixel_read.channel,
        )
        self.dma_palette_rst.config(
            count=1,
            read=self.rst_addr_ptr,
            write=DMA_BASE_4 + DMA_READ_ADDR_AL1,
            ctrl=dma_palette_rst_ctrl,
        )

        """ Row Size DMA channel - CH #7 - Sends the new row size to calculate another offset ------------------- """
        rs_write = PIO1_TX1
        rs_inc_write = False

        dma_row_size_ctrl = self.dma_row_size.pack_ctrl(
            size=2,
            inc_read=False,
            inc_write=rs_inc_write,
            treq_sel=DREQ_PIO1_TX1,
            chain_to=self.dma_row_start.channel,
        )
        self.dma_row_size.config(
            count=1,
            read=self.row_size,
            write=rs_write,
            ctrl=dma_row_size_ctrl,
        )

        """ Row Start DMA channel - CH #8 - Reloads the write reg of pixel_out to the start of the next row  """

        rsc_write = DMA_BASE_5 + DMA_WRITE_ADDR
        rsc_inc_write = False

        dma_row_start_ctrl = self.dma_row_start.pack_ctrl(
            size=2,
            inc_read=False,
            inc_write=rsc_inc_write,
            treq_sel=DREQ_PIO1_RX1,
            chain_to=self.dma_palette_rst.channel,
        )
        self.dma_row_start.config(
            count=1,
            read= PIO1_RX1,
            write=rsc_write,
            ctrl=dma_row_start_ctrl,
        )

        """ Horizontal Upscale channel - CH #9 - uses a ring buffer t provide a pattern of pixel repetition for scaling """

        if self.debug_buffer_enable:
            scale_write = addressof(self.debug_bytes)
            scale_inc_write = True
        else:
            scale_write = DMA_BASE_5 + DMA_TRANS_COUNT
            scale_inc_write = False

        dma_h_scale_ctrl = self.dma_h_scale.pack_ctrl(
            size=2,
            inc_read=True,
            inc_write=scale_inc_write,
            chain_to=self.dma_palette_rst.channel,
            ring_sel=0,
            ring_size=4,
        )

        self.dma_h_scale.config(
            count=1,
            read=self.h_scale_ptr,
            write=scale_write,
            ctrl=dma_h_scale_ctrl,
            # trigger=True
        )

    def img_end_irq_handler(self, irq_obj):
        if self.debug:
            print("<<<<<< IMG END IRQ - Triggered >>>>>>")
        self.read_complete = True

    def config_dma(self, image, x, y, width, height):
        display = self.display
        num_pixels = width * height
        write_addr_base = self.write_addr_base

        write_addr = display.write_addr
        write_offset = ((y * display.width) + x) * 2  # since the display is 16 bit, we multiply x 2
        write_addr += write_offset
        # self.write_addr = write_addr

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
            print(f"\tpalette_addr: 0x{addressof(self.color_addr_list):08x}")
            print(f"\tpalette_addr_ptr: 0x{addressof(self.rst_addr_ptr):08x}")
            print(f"\trow_size: 0x{self.row_size[0]:08x}")


    def show(self, image: Image, x, y, width, height, scale=1):
        """ ----------- Set variable per-image configuration on all the DMA channels -------------- """
        display = self.display
        num_pixels = int(width * height)
        row_tx_count = int(width + self.h_skew) # Adding / substracting can apply skew to the image
        self.write_start_addr = addressof(display.write_framebuf)
        self.row_size[0] = display.width * 2

        write_offset = ((y * self.display.width) + x) * 2 # since the display is 16 bit, we multiply x 2
        self.write_addr = self.write_start_addr + write_offset


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
        self.dma_row_read.read = image.pixel_bytes_addr             # CH2
        self.dma_row_read.count = (num_pixels // 8)
        self.dma_pixel_read.count = row_tx_count                    # CH3
        self.dma_pixel_out.read = self.palette_buffer               # CH5
        self.dma_pixel_out.write = self.write_addr
        self.dma_pixel_out.count = 1                                # We can set the horizontal scale here (upscaling)
        self.dma_palette.read = self.color_addr_list                # CH4
        self.dma_palette_rst.read = self.rst_addr_ptr               # CH6
        self.dma_row_start.count = 1                                # CH8 - not sure why we need count=2, but that's what works
        prof.end_profile('scaler.dma_init_values')

        """ Lets setup the scaling pattern """
        if scale > 100:
            if scale > 200:
                scale = 200
            rel_scale = scale - 100
            rel_scale = rel_scale / 100
            # idx = round(rel_scale * (len(self.h_patterns)))
            # if idx >= len(self.h_patterns):
            #     idx = len(self.h_patterns) - 1
            idx=0

            self.h_scale_ptr = self.h_patterns_ptr[idx]

            ctrl = self.dma_h_scale.unpack_ctrl(self.dma_h_scale.ctrl)
            ctrl['ring_sel'] = True
            ctrl['ring_size'] = 1

            self.dma_h_scale.pack_ctrl(**ctrl)

        if self.debug:
            for i in range(2, 10):
                idx = i - 2
                ch = self.channels[idx]
                ch_alias = self.channel_names[idx]
                ch_alias = ch_alias.upper()
                self.dbg.debug_dma(ch, ch_alias, 'before_start', idx + 2)
                self.dbg.debug_pio_status()
                print("- - - - - - - - - - - - - - - - - - - - - ")
                self.dbg.debug_register()

        self.read_complete = False

        """ State Machine startup -----------------------"""
        prof.start_profile('scaler.start_pio')
        self.sm_indices.restart()
        self.sm_row_start.restart()
        self.sm_row_start.put(self.write_addr)

        prof.end_profile('scaler.start_pio')

        """ We only need to kick off the channels that don't have any other means to get started (like chain_to)"""
        prof.start_profile('scaler.start_dma')
        self.dma_pixel_read.active(1)
        self.dma_row_read.active(1)

        prof.end_profile('scaler.start_dma')

        if self.debug:
            self.dbg.debug_fifos()

        prof.start_profile('scaler.inner_loop')
        """ As far as DMA goes, active and busy are the same thing (i think)"""
        while (not self.read_complete):
            if self.debug:
                for i in range(2, 10):
                    idx = i - 2
                    ch = self.channels[idx]
                    ch_alias = self.channel_names[idx]
                    ch_alias = ch_alias.upper()
                    self.dbg.debug_dma(ch, ch_alias, 'in_loop', idx + 2)
                    self.dbg.debug_pio_status()
                    print("- - - - - - - - - - - - - - - - - - - - - ")
                    print()
                    self.dbg.debug_register()
                    self.dbg.debug_fifos()

            if self.debug_buffer_enable:
                print("----------------------------------------------")
                print("DEBUG BUFFER:")
                self.dbg.debug_buffer(self.debug_bytes)

            pass

        prof.end_profile('scaler.inner_loop')

        if self.debug:
            print("<<<-------- FINISHED READING IMAGE ---------->>>")

            for i in range(2, 10):
                idx = i - 2
                ch = self.channels[idx]
                ch_alias = self.channel_names[idx]
                ch_alias = ch_alias.upper()
                self.dbg.debug_dma(ch, ch_alias, 'post_dma', idx + 2)
                self.dbg.debug_pio_status()
                print("- - - - - - - - - - - - - - - - - - - - - ")
                self.dbg.debug_register()

        # return False # debug
        time.sleep_ms(100)
        self.stop_scaler()
        # self.update_scale()

    def stop_scaler(self):
        self.dma_row_read.active(0)
        self.dma_pixel_read.active(0)
        self.dma_palette.active(0)
        self.dma_palette_rst.active(0)
        self.dma_pixel_out.active(0)
        self.dma_row_start.active(0)
        self.dma_row_size.active(0)
        self.dma_h_scale.active(0)
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
        self.dma_pixel_read.close()
        self.dma_palette.close()
        self.dma_palette_rst.close()

        self.dma_pixel_out.close()
        self.dma_row_start.close()
        self.dma_row_size.close()
        self.dma_h_scale.close()
