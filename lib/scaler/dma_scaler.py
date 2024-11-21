import math
import micropython

from scaler.scaler_interp import SpriteScaler
from scaler.scaler_interp_pio import indexed_sprite_handler

micropython.alloc_emergency_exception_buf(100)

import utime

from scaler.dma_scaler_debug import ScalerDebugger
from scaler.dma_scaler_pio import *
from uctypes import addressof

from machine import Pin, mem32

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
    write_addr = None
    h_scale = 1
    v_scale = 1
    h_patterns_int = []
    v_patterns_up_int = []
    v_patterns_down_int = []
    v_patterns_all = []
    v_patterns_buf_all = []

    h_patterns_ptr = []
    h_pattern_buf_all = []

    v_patterns_up_ptr = []
    scale_index = 0
    v_scale_up_index = 0
    v_scale_down_index = 0
    h_scale_index = 0
    last_scale_shift = 0 #
    scale_shift_freq = 20 # every X ms, scale shifts one step
    bytes_per_pixel = 2
    sm_palette_idx = None
    sm_row_start = None
    sm_vert_scale = None
    sm_indexed_scaler = None
    row_tx_count = 0

    debug = True
    debug_buffer_enable = False
    dbg: ScalerDebugger = None

    dma_row_read = None
    read_finished = True

    h_skew = 0

    channel_names = {
        "2": 'row_read',
        "3": 'color_addr',
        "4": 'pixel_out',
        "5": 'h_scale',
        "6": 'row_size',
        "7": 'row_start',
        "8": 'v_scale',
    }
    channels = {}

    h_scale_ptr = None # Ptr to the current scale pattern array
    v_scale_down_ptr = None
    scale_index_flip = 1

    dma_pixel_read = None
    dma_palette = None
    dma_pixel_out = None
    all_h_patterns = []

    def __init__(self, display, palette_size,
                 channel2, channel3, channel4, channel5, channel6, channel7, channel8, channel9):
        self.write_addr_base = display.write_addr

        """ Set the DMA fractional timer x/y * sysclock"""
        # frac_x = bytearray([0, 1])
        # frac_y = bytearray([0, 32])
        # regval = frac_y + frac_x
        # mem32[DMA_FRAC_TIMER] = 0x0020001

        """ DMA Channels"""
        self.dma_row_read = channel2
        self.dma_color_addr = channel3
        self.dma_pixel_out = channel4
        self.dma_h_scale = channel5
        self.dma_row_size = channel6
        self.dma_row_start = channel7
        self.dma_v_scale = channel8
        # self.dma_row_addr = channel9
        self.dma_interp = channel9

        self.channels = {
            "2" : self.dma_row_read,
            "3": self.dma_color_addr,
            "4" : self.dma_pixel_out,
            "5": self.dma_h_scale,
            "6" : self.dma_row_size,
            "7" : self.dma_row_start,
            "8" : self.dma_v_scale,
        }

        """ Init static data buffers for the DMA channels """

        """ Row size must always be the same!! (screen width) """
        row_size_buff = bytearray(4)
        self.row_size = array("L", row_size_buff)
        self.row_size[0] = int(display.width * 2) - 1 # screen width

        print("~ CONTENTS OF ROW_SIZE ARRAY ~")
        print(f"0x{self.row_size[0]:08x}")

        print(f"SETTING ROW_SIZE TO {display.width * 2} =  {self.row_size[0]}")

        self.display = display
        self.write_start_addr = addressof(self.display.write_framebuf)

        self.screen_width = self.display.width
        self.screen_height = self.display.height
        self.palette_size = palette_size

        # """ SM0: Pixel demuxer / index reader """
        # self.sm_palette_idx = rp2.StateMachine(4)               # 1st SM in PIO1
        #
        # """ SM1: Row start address generator (write) """
        # self.sm_row_start = rp2.StateMachine(5)             # 2nd SM in PIO1
        #
        # """ SM2:  Row start address generator (read) """
        # self.sm_vert_scale = rp2.StateMachine(6)             # 3nd SM in PIO1


        self.sm_indexed_scaler = rp2.StateMachine(4)               # 1st SM in PIO1 (#0)

        """ Debug Buffer """
        if self.debug:
            self.dbg = ScalerDebugger(
                self.sm_palette_idx,
                self.sm_row_start,
                self.sm_vert_scale,
                self.sm_indexed_scaler,
                self.dma_interp)
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
            [1, 1, 1, 1, 1, 1, 1, 1],       # 0s don't work at the moment
            [1, 1, 1, 1, 2, 1, 1, 1],       # 12.5%
            [1, 1, 2, 1, 1, 1, 2, 1],       # 25%
            [1, 1, 2, 1, 1, 2, 1, 2],       # 37.5%
            [1, 2, 1, 2, 1, 2, 1, 2],       # 50%
            [2, 1, 2, 2, 1, 2, 1, 2],       # 62.5%
            [2, 1, 2, 2, 2, 1, 2, 2],       # 75%
            [2, 2, 2, 2, 1, 2, 2, 2],       # 87.5%
            [2, 2, 2, 2, 2, 2, 2, 2],       # 100%
            [2, 2, 2, 2, 3, 2, 2, 2],       # 112.5%
            [2, 2, 3, 2, 2, 2, 3, 2],       # 135%
            [2, 2, 3, 2, 2, 3, 2, 3],       # 137.5%
            [2, 3, 2, 3, 2, 3, 2, 3],       # 150%
            [3, 2, 3, 3, 2, 3, 2, 3],       # 162.5%
            [3, 2, 3, 3, 3, 2, 3, 3],       # 175%
            [3, 3, 3, 3, 2, 3, 3, 3],       # 187.5%
            [3, 3, 3, 3, 3, 3, 3, 3],       # 200%
            [3, 3, 3, 3, 4, 3, 3, 3],       # 212.5%
            [3, 3, 4, 3, 3, 3, 4, 3],       # 235%
            [3, 3, 4, 3, 3, 4, 3, 4],       # 237.5%
            [3, 4, 3, 4, 3, 4, 3, 4],       # 250%
            [4, 3, 4, 4, 3, 4, 3, 4],       # 262.5%
            [4, 3, 4, 4, 4, 3, 4, 4],       # 275%
            [4, 4, 4, 4, 3, 4, 4, 4],       # 287.5%
            [4, 4, 4, 4, 4, 4, 4, 4]        # 300%
        ]
        self.h_patterns_int = h_patterns_int

        v_patterns_up_int = [
            # Vertical upscaling patterns. Doubled up because there are less total combinations
            [1, 1, 1, 1, 1, 1, 1, 1],  # 100%
            [0, 1, 1, 1, 1, 1, 1, 1],
            [0, 1, 1, 1, 1, 1, 1, 1],
            [0, 1, 1, 1, 0, 1, 1, 1],
            [0, 1, 1, 1, 0, 1, 1, 1],
            [0, 1, 1, 0, 1, 0, 1, 1],
            [0, 1, 1, 0, 1, 0, 1, 1],
            [0, 1, 0, 1, 0, 1, 0, 1],  # 200%
            [0, 1, 0, 1, 0, 1, 0, 1],  # 200%'
            # [0, 1, 0, 1, 0, 1, 0, 1],  # 200%'
            # [0, 1, 0, 0, 1, 0, 0, 1],
            # [0, 1, 0, 0, 1, 0, 0, 1],
            # [0, 1, 0, 0, 1, 0, 0, 0],
            # [0, 1, 0, 0, 1, 0, 0, 0],
            # [0, 0, 0, 1, 0, 0, 0, 0],  # 400%
            # [0, 0, 0, 1, 0, 0, 0, 0],  # 400%
            # [0, 0, 0, 1, 0, 0, 0, 0],  # 400%
        ]
        self.v_patterns_up_int = v_patterns_up_int

        v_patterns_down_int = [
            [1, 1, 1, 1, 1, 1, 1, 1],
            [0, 0, 0, 0, 1, 0, 0, 0],  # 12.5%
            [0, 0, 1, 0, 0, 0, 1, 0],  # 25%
            [0, 0, 1, 0, 0, 1, 0, 1],  # 37.5%
            [0, 1, 0, 1, 0, 1, 0, 1],  # 50%
            [1, 0, 1, 1, 0, 1, 0, 1],  # 62.5%
            [1, 0, 1, 1, 1, 0, 1, 1],  # 75%
            [1, 1, 1, 1, 0, 1, 1, 1],  # 87.5%
            [1, 1, 1, 1, 1, 1, 1, 1]  # 100%
        ]
        self.v_patterns_down_int = v_patterns_down_int

        self.pattern_size = pattern_size = 16 # num elements in one pattern

        """ We need to turn these lists into basic arrays so that the pointers are easier to pass to DMA """
        self.h_patterns_ptr = array('L', [0x00000000] * len(h_patterns_int))
        self.v_patterns_down_ptr = array('L', [0x00000000] * len(v_patterns_down_int))
        self.v_patterns_up_ptr = array('L', [0x00000000] * len(v_patterns_up_int))

        # print("//// SCALING PATTERNS (horiz upscaling) \\\\\\\\")
        # Store patterns as 32-bit values, but only use values 1-4
        for i, scale_pattern in enumerate(h_patterns_int):
            # Get 32-byte aligned buffer for 8 x 4-byte elements
            # h_pattern_buf = aligned_buffer(8 * 4, alignment=32)
            h_pattern_buf = bytearray(8 * 4)
            h_pattern = array('L', h_pattern_buf)

            # Debug verification
            pattern_addr = addressof(h_pattern)

            # print(f"Pattern buffer address: 0x{addressof(h_pattern):08x}")
            # print(f"Buffer alignment: {addressof(h_pattern) % 32}")  # Should be 0 for 32-byte alignment

            for j, element in enumerate(scale_pattern):
                h_pattern[j] = int(element)  # Values 1-4 stored in 32-bit words

            self.h_patterns_ptr[i] = addressof(h_pattern)
            self.all_h_patterns.append(h_pattern)

        # print("//// SCALING PATTERNS (vertical downscaling) \\\\\\\\")
        for i, scale_pattern in enumerate(v_patterns_down_int):
            v_pattern_buf = bytearray(pattern_size * 4)
            v_pattern = array('L', v_pattern_buf)

            for j, value in enumerate(scale_pattern):
                v_pattern[j] = int(value)

            self.v_patterns_down_ptr[i] = addressof(v_pattern)
            # all_patterns.append(v_pattern)
            # all_buffers.append(v_pattern_buf)

        # print("//// SCALING PATTERNS (vertical upscaling) \\\\\\\\")
        for i, v_scale_pattern in enumerate(v_patterns_up_int):
            v_pattern_up_buf = bytearray(pattern_size * 4)
            v_pattern_up = array('L', v_pattern_up_buf)

            for j, value in enumerate(v_scale_pattern):
                v_pattern_up[j] = int(value)

            self.v_patterns_up_ptr[i] = addressof(v_pattern_up)
            self.v_patterns_all.append(v_pattern_up)
            self.v_patterns_buf_all.append(v_pattern_up_buf)

        self.h_scale_ptr = self.h_patterns_ptr[3]
        self.v_scale_down_ptr = self.v_patterns_down_ptr[0]
        self.v_scale_up_ptr = self.v_patterns_up_ptr[0]

        self.h_scale_index = 0
        self.v_scale_up_index = 0
        self.v_scale_down_index = 0

        print(f"INIT H PATTERN ADDR: 0x{self.h_scale_ptr:08x}")
        print(f"INIT V PATTERN ADDR: 0x{self.v_scale_down_ptr:08x}")

        self.write_start_addr = addressof(display.write_framebuf) # This is probably where the frame flickering gets resolved

        self.init_pio()
        print(f"Screen dimensions: {self.screen_width}x{self.screen_height}")
        # self.init_dma()
        # self.init_sniff()

    def init_pio(self):
        # Set up the PIO state machines
        # freq = 80 * 1000 * 1000
        freq = 5 * 1000
        # freq = 200 * 1000
        # freq = 40 * 1000
        # freq = 25 * 1000

        """ SM0: Pixel demuxer / palette reader """
        # sm_indices = self.sm_palette_idx
        # sm_indices.init(
        #     read_palette,
        #     freq=freq,
        # )

        """ SM1:  Row start address generator (write) """
        # sm_row_start = self.sm_row_start
        # sm_row_start.init(
        #     row_start,
        #     freq=freq,
        # )

        """ SM2:  Row start address generator (read) """
        # sm_vert_scale = self.sm_vert_scale
        # sm_vert_scale.init(
        #     row_start,
        #     freq=freq,
        # )


    def init_dma(self):
        """ Configure and initialize the DMA channels general settings (once only) """

        """ CH #2 - Image Read DMA channel - (feeds SM0) --------------------------------------- """
        dma_row_read_ctrl = self.dma_row_read.pack_ctrl(
            size=0,
            inc_read=True,
            inc_write=False,
            treq_sel=DREQ_PIO1_TX0,
            chain_to=self.dma_row_addr.channel,
            # sniff_en=True,
            # bswap=True,
        )
        self.dma_row_read.config(
            count=0,  # To be set later: img pixels per row // 2
            read=0,  # To be set later: memory address of the first pixel of the framebuffer of the sprite
            write=PIO1_TX0,
            ctrl=dma_row_read_ctrl,
        )


        """ CH #3 - Color address - pass the resulting palette address to the pixel writer """
        dma_color_addr_ctrl = self.dma_color_addr.pack_ctrl(
            size=2,
            inc_read=False,
            inc_write=False,
            treq_sel=DREQ_PIO1_RX0,
            high_pri=True,
            # chain_to=self.dma_pixel_out.channel,
        )

        self.dma_color_addr.config(
            count=1,
            read=PIO1_RX0,
            write=DMA_BASE_4 + DMA_READ_ADDR_TRIG,
            ctrl=dma_color_addr_ctrl,
        )

        """ CH #4 - Pixel out DMA channel ---------------------- """
        dma_pixel_out_ctrl = self.dma_pixel_out.pack_ctrl(
            size=1,  # output one pixel at a time (2 bytes)
            inc_read=False,
            inc_write=True,
            high_pri=True,
            chain_to=self.dma_h_scale.channel,
        )

        self.dma_pixel_out.config(
            count=1,  # Increasing this above 1 will stretch pixels horizontally for upscaling
            read=0,
            write=0,  # To be set later
            ctrl=dma_pixel_out_ctrl,
        )

        """CH #5 - Horizontal Upscale channel - uses a ring buffer t provide a pattern of pixel repetition for scaling """
        dma_h_scale_ctrl = self.dma_h_scale.pack_ctrl(
            size=2,
            inc_read=True,
            inc_write=False,
            chain_to=self.dma_color_addr.channel,
            high_pri=True,
            ring_sel=0,
            ring_size=4,
        )

        self.dma_h_scale.config(
            count=1,
            read=self.h_scale_ptr,
            write=DMA_BASE_4 + DMA_TRANS_COUNT,
            ctrl=dma_h_scale_ctrl,
        )

        print(f"> DMA h_scale read addr: 0x{self.dma_h_scale.read:08x}")
        print(f"> DMA h_scale read increment: {self.dma_h_scale.ctrl >> 4 & 1}")
        # print(f"> DMA h_scale ring size: {1 << self.dma_h_scale.ctrl >> 19 & 0xf} bytes")

        """ CH #6 - Row Size / pattern DMA channel - Sends the new row size to calculate another offset ------------------- """

        dma_row_size_ctrl = self.dma_row_size.pack_ctrl(
            size=2,
            inc_read=True,
            inc_write=False,
            # treq_sel=DREQ_PIO1_TX1,
            treq_sel=DREQ_TIMER_0,
            chain_to=self.dma_row_start.channel,
            ring_sel=0,
            ring_size=4
        )
        self.dma_row_size.config(
            count=1,
            read=0,
            write=PIO1_TX1,
            ctrl=dma_row_size_ctrl,
        )

        """ CH #7 - Row Start DMA channel - Reloads the write reg of pixel_out to the start of the next row  """

        row_s_write = DMA_BASE_4 + DMA_WRITE_ADDR
        row_s_inc_write = False

        dma_row_start_ctrl = self.dma_row_start.pack_ctrl(
            size=2,
            inc_read=False,
            inc_write=row_s_inc_write,
            treq_sel=DREQ_PIO1_RX1,
            chain_to=self.dma_row_read.channel,
        )
        self.dma_row_start.config(
            count=1,
            read=PIO1_RX1,
            write=row_s_write,
            ctrl=dma_row_start_ctrl,
        )

        """ CH #8 - Vert Scale DMA channel - Reconfigures the start addr of the read head, in order to implement
          vertical upscaling."""
        dma_v_scale_ctrl = self.dma_v_scale.pack_ctrl(
            size=2,
            inc_read=True,
            inc_write=False,
            treq_sel=DREQ_PIO1_TX2,
            ring_sel=0,
            ring_size=4,
            irq_quiet=False
        )
        self.dma_v_scale.config(
            count=0,  # TBD
            read=self.v_scale_up_ptr,
            write=PIO1_TX2,
            ctrl=dma_v_scale_ctrl,
        )
        self.dma_v_scale.irq(handler=self.irq_img_end)

        """ CH #9 - New DMA channel to update CH2's read address from vertical scaling SM output"""
        dma_row_addr_ctrl = self.dma_row_addr.pack_ctrl(
            size=2,  # 32-bit addresses from PIO
            inc_read=False,  # Reading single value from PIO RX FIFO
            inc_write=False,  # Writing to DMA control register
            treq_sel=DREQ_PIO1_RX2,  # Triggered when vert scale SM outputs address
            chain_to=self.dma_row_size.channel  # Trigger pixel read after address update
        )

        self.dma_row_addr.config(
            count=1,  # Single address update per row
            read=PIO1_RX2,  # Read from vertical scale SM output
            write=DMA_BASE_2 + DMA_READ_ADDR,  # Write to CH2's read address trigger
            ctrl=dma_row_addr_ctrl
        )

    def reset(self):
        """Clean shutdown and reset sequence"""
        # 1. Disable DMA first to stop new requests
        self.dma_v_scale.active(0)  # Stop the trigger for vertical scaling
        self.dma_row_read.active(0)  # Stop pixel reads
        # self.dma_row_addr.active(0)
        self.dma_row_size.active(0)

        # 2. Stop state machines to prevent new DREQ triggers
        # self.sm_vert_scale.active(0)
        # self.sm_row_start.active(0)
        # self.sm_palette_idx.active(0)

        # 3. Now disable remaining DMA channels
        self.dma_color_addr.active(0)
        self.dma_pixel_out.active(0)
        self.dma_h_scale.active(0)

        # 4. Reset state machines to known state
        # for sm in [self.sm_palette_idx, self.sm_row_start, self.sm_vert_scale]:
        #     sm.restart()
        self.sm_indexed_scaler.restart()

        # 5. Reset write address for next frame
        self.write_start_addr = addressof(self.display.write_framebuf)


    def dma_handler_debug(self, irq):
        print("  >>>> DMA TRANSFER <<<< complete for: #", end='')
        print(irq.channel)


    def irq_img_end(self, dma_ch):
        dma_ch.active(0)

        """Wait for all DMA channels and processing to complete"""
        # wait for state machine FIFOS
        while (self.sm_palette_idx.tx_fifo()
               or self.sm_row_start.tx_fifo()
               or self.sm_vert_scale.tx_fifo()
        ):
            pass

        # First wait for main chain to complete
        while (
               self.dma_row_read.active() or
               # self.dma_row_addr.active() or
               self.dma_row_size.active() or
               self.dma_row_start.active()
            ):
            pass

        # Then wait for pixel processing chain
        while (self.dma_pixel_out.active() or
               self.dma_h_scale.active()):
            pass

        self.reset()
        if self.debug:
            print()
            print("<<<<<< IMG END IRQ - Triggered / Read Complete >>>>>>")
            print()
        self.read_finished = True

    def config_dma(self, image, x, y, width, height):
        display = self.display
        self.num_pixels = num_pixels = width * height

        write_addr_base = self.write_addr_base
        write_offset = (((y * display.width) + x) * 2) - 8  # since the display is 16 bit, we multiply x 2
        self.write_addr = write_addr_base + write_offset

        if self.debug:
            self.dbg.debug_addresses(display, image, x, y)


    def show(self, image: Image, x, y, width, height, scale=1):
        """ Version that uses the interpolator """

        if self.debug:
            debugger = self.dbg
        else:
            debugger = False

        if self.debug:
            print(f"IMAGE READ ADDR: 0x{image.pixel_bytes_addr:08x}")
            print(f"IMAGE SCALE: {scale:04f}")
            print(f"IMAGE WIDTH (px): {width}")
            print(f"IMAGE HEIGHT (px): {height}")
            print(f"IMAGE ACTUAL HEIGHT (px): {height}")
            print(f"IMAGE VSCALE: {scale:04f}")

        self.config_dma(image, x, y, width, height)

        self.read_finished = False
        scaler = SpriteScaler(self.display, self.sm_indexed_scaler, self.dma_interp, debugger)
        write_offset = (((y * self.display.width) + x) * 2) - 8  # since the display is 16 bit, we multiply x 2
        self.write_addr = self.display.write_addr + write_offset

        # Draw sprite scaled 2x horizontally, 1.5x vertically
        # scaler.draw_scaled_sprite(image, x=10, y=20, h_scale=2.0, v_scale=1.5)
        # scaler.draw_scaled_sprite(image, x=0, y=0)
        scaler.draw_test_pattern(image)


    def _show(self, image: Image, x, y, width, height, scale=1):
        """Adjust coords for scale"""
        x = x - self.h_scale_index + 1
        y = y - self.v_scale_up_index + 1

        # Ensure previous frame is complete
        if not self.read_finished:
            return

        self.read_finished = False

        byte_width = math.ceil(image.width // 2) # Input width divided by 2 since we read 2 pixels at once

        if self.debug:
            # Verify pattern contents
            pattern_addr = self.dma_v_scale.read
            pattern_size = 8
            print("V-Scale Pattern Values:")
            for i in range(pattern_size):
                val = mem32[pattern_addr + (i * 4)]
                print(f"* Pattern[{i}]: {val}")

        if self.debug:
            print("Initial SM2 setup:")
            print(f"Base read addr: 0x{image.pixel_bytes_addr:08x}")
            print(f"Row width: {byte_width}")
            print(f"DMA #8 pattern addr: 0x{self.v_scale_up_ptr:08x}")



        """ ----------- Set variable per-image configuration on all the DMA channels -------------- """
        prof.start_profile('scaler.prep_img_vars')

        h_scale = sum(self.h_patterns_int[self.h_scale_index]) / self.pattern_size
        # Adjust row transfer count for doubled pixels

        # Double check total pixel count
        # actual_width = sum(self.h_patterns_int[self.h_scale_index])
        # actual_height = round(height * v_scale)

        row_tx_count = byte_width # for 1byte tx size
        # v_scale = sum(self.v_patterns_down_int[0]) / self.pattern_size
        v_scale = 1

        # actual_width = int(width * h_scale)

        up_pattern = self.v_patterns_up_int[self.v_scale_up_index]
        actual_height = self.get_upscaled_height(height, up_pattern)

        if self.debug:
            print(f"-- HEIGHT: {height} / IDX: [{self.v_scale_up_index}] / ACTUAL=HEIGHT: {actual_height}")

        # row_tx_count = int(width + self.h_skew) # Adding / substracting can apply skew to the image
        prof.end_profile('scaler.prep_img_vars')

        prof.start_profile('scaler.config_dma')
        self.config_dma(image, x, y, width, height, actual_height)
        prof.end_profile('scaler.config_dma')

        if self.debug:
            print(f"IMAGE WIDTH (px): {width}")
            print(f"IMAGE HSCALE: {h_scale:04f}")
            print(f"IMAGE SUM/SIZE: {sum(self.h_patterns_int[0])}/{self.pattern_size}")
            print(f"IMAGE HEIGHT (px): {height}")
            print(f"IMAGE ACTUAL HEIGHT (px): {actual_height}")
            print(f"IMAGE VSCALE: {v_scale:04f}")
            print(f"ROW TX COUNT (32bit): {row_tx_count}")
            print(f"H SCALE IDX: {self.h_scale_index}")
            print(f"V SCALE IDX: {self.v_scale_up_index}")

        # print(f"SCALER WRITING TO WRITE BUFF @:{self.write_addr_base:08x}")
        color_addr = addressof(image.palette_bytes)

        prof.start_profile('scaler.dma_init_values')

        self.dma_row_read.count = row_tx_count                         #   for 1byte width
        # self.dma_color_addr.count = image.width * image.height                        # CH3
        # self.dma_color_addr.count = self.num_pixels

        """ CH4 """
        self.dma_pixel_out.read = color_addr
        self.dma_pixel_out.write = self.write_addr
        self.dma_pixel_out.count = 1                                    # We can set the horizontal scale here (upscaling)

        self.dma_h_scale.read = self.h_patterns_ptr[self.h_scale_index]                              # CH5 -
        self.dma_h_scale.count = 1                             # CH5 -
        self.dma_row_size.read = self.v_patterns_down_ptr[self.v_scale_down_index]                         # CH6 -
        self.dma_row_size.count = 1

        """ CH 8"""
        # self.dma_v_scale.count = actual_height
        self.dma_v_scale.count = height - 1
        self.dma_v_scale.read = self.v_patterns_up_ptr[self.v_scale_up_index]

        prof.end_profile('scaler.dma_init_values')

        """ CH 9"""
        self.dma_row_addr.count = 1

        if self.debug:
            for idx in self.channel_names.keys():
                self.dbg.debug_all_dma_channels(idx, 'BEFORE_START')

        """ SNIFFING CONFIG """
        # self.config_sniff(height * byte_width)

        """ STATE MACHINES INITIAL DATA AND STARTUP -----------------------"""

        prof.start_profile('scaler.start_pio')

        # sm.irq(lambda p: print(time.ticks_ms()))
        """ Prime color SM with first palette addr. """
        self.sm_palette_idx.put(color_addr)
        if self.debug:
            print(f"~~~ Priming SM0 with {color_addr:08x} ~~~")

        """
        Prime row start SM with:
        1. Write framebuffer addr
        2. Row size (0xC0 = 192 bytes per row for write)
        """
        self.sm_row_start.put(self.write_addr)
        self.sm_row_start.put(self.row_size[0])  # full display width
        if self.debug:
            print(f"~~~ Priming SM1 (write) with addr:{self.write_addr:08x} and row size:{self.row_size[0]:08x} ~~~")

        """
        Prime vertical scale SM with:
        1. Image data read addr
        2. image row size (width/2 since we read 2 pixels at a time)
        3. 1st pattern
        """
        self.sm_vert_scale.put(image.pixel_bytes_addr)
        self.sm_vert_scale.put(byte_width - 1)

        if self.debug:
            print(f"~~~ Priming SM2 (read) with addr:{image.pixel_bytes_addr:08x} and row size (bytes):{byte_width} ~~~")

        self.sm_palette_idx.active(1)
        self.sm_row_start.active(1)
        self.sm_vert_scale.active(1)

        prof.end_profile('scaler.start_pio')

        if self.debug:
            print("- Starting DMA channels -")

        """ DMA - We only need to kick off the channels that don't have any other means to get started (like chain_to)"""
        prof.start_profile('scaler.start_dma')

        """ Specific Start sequence order is very important """
        self.dma_row_addr.active(1)  # Start of chain
        self.dma_v_scale.active(1)
        self.dma_h_scale.active(1)  # Horizontal scaling
        self.dma_color_addr.active(1)  # Color lookup

        # self.dma_pixel_out.active(1)  # Pixel output

        if self.debug:
            print("- DMA channels started -")

        prof.end_profile('scaler.start_dma')

        if self.debug:
            self.dbg.debug_fifos()

        prof.start_profile('scaler.inner_loop')
        """ As far as DMA goes, active and busy are the same thing (i think)"""
        if self.debug:
            print("- Entering inner write loop -")

        while (not self.read_finished):
            if self.debug:
                for idx in self.channel_names.keys():
                    self.dbg.debug_all_dma_channels(idx, 'IN_LOOP')

            if self.debug_buffer_enable:
                print(self.dbg)
                print("----------------------------------------------")
                print("DEBUG BUFFER:")
                self.dbg.debug_buffer(self.debug_bytes)

        prof.end_profile('scaler.inner_loop')

        if self.debug:
            print("<<<<-------- FINISHED READING IMAGE ---------->>>>")

        # self.update_scale()

    def stop_scaler(self):
        self.sm_palette_idx.active(0)
        self.sm_row_start.active(0)
        self.sm_vert_scale.active(0)

        if self.debug:
            pending_counts = [
                'dma_row_read',
                'dma_row_start',
                'dma_row_size',
                'dma_color_addr',
                'dma_pixel_out',
                'dma_h_scale',
                'dma_v_scale']

            for one_dma in pending_counts:
                attr = getattr(self, one_dma)
                active = "ACTIVE" if attr.active() else ""
                print(f"{one_dma: < 16}   TX:{attr.count} \t{active}")


        self.dma_row_read.active(0)
        self.dma_row_start.active(0)
        self.dma_color_addr.active(0)
        self.dma_pixel_out.active(0)
        self.dma_row_size.active(0)
        self.dma_h_scale.active(0)
        self.dma_v_scale.active(0)
        self.dma_row_addr.active(0)

        print()

    def update_scale(self):
        """ shift the scale"""
        max_h_idx = len(self.h_patterns_ptr) - 1
        max_v_idx = len(self.v_patterns_up_ptr) - 1

        # print(f"MAXIDX::: {max_idx}")
        # max_idx = 8

        diff = utime.ticks_diff(utime.ticks_ms(), self.last_scale_shift)

        if diff > self.scale_shift_freq:
            prof.start_profile('scaler.scale_shift')

            """
            Animates all 4 scaling operations that the scaler can do:
            - Horizontal upscaling
            - Horizontal downscaling
            - Vertical upscaling
            - Vertical downscaling
            """
            self.h_scale_index += (1 * self.scale_index_flip)
            # self.v_scale_up_index += (1 * self.scale_index_flip)
            # self.v_scale_down_index += (1 * self.scale_index_flip)

            """ HORIZ index """
            if self.h_scale_index >= max_h_idx:
                self.h_scale_index = max_h_idx
                self.scale_index_flip = self.scale_index_flip * -1

            if self.h_scale_index < 0:
                self.h_scale_index = 0
                self.scale_index_flip = self.scale_index_flip * -1

            # """ VERT index """
            # if self.v_scale_up_index >= max_v_idx:
            #     self.v_scale_up_index = max_v_idx
            #     self.scale_index_flip = self.scale_index_flip * -1
            #
            # if self.v_scale_up_index < 0:
            #     self.v_scale_up_index = 0
            #     self.scale_index_flip = self.scale_index_flip * -1

            if self.debug:
                print(f"=== Shifted scale to: {self.h_scale_index}")

            self.last_scale_shift = utime.ticks_ms()

            prof.end_profile('scaler.scale_shift')

    def get_upscaled_height(self, height, up_pattern):
        """ Calculate the actual height of a sprite to be drawn, given the original height, and the upscaling pattern.
        The pattern is made of 1s and 0s, where 1 means normal 1:1 row, and 0 means repeat row (ie: all zeros is 2x)"""

        pattern_len = len(up_pattern)
        one_pattern_zeros = up_pattern.count(0)
        one_pattern_ones = up_pattern.count(1)
        pattern_count = int(height/pattern_len)

        carry = height % pattern_len
        carry_zeros = up_pattern[0:carry].count(0)
        carry_ones = up_pattern[0:carry].count(1)

        zeros = (one_pattern_zeros * pattern_count * 2) + carry_zeros
        ones = (one_pattern_ones * pattern_count) + carry_ones
        new_height = (zeros) + height

        if self.debug:
            print(f"UPPATTERN IS --> {up_pattern}")
            print(f"WITH {one_pattern_zeros} zeros and {one_pattern_ones} ones (pattern count: {pattern_count})")
            print(f"CARRY: {carry} / CARRY_z: {carry_zeros} / CARRY_0: {carry_zeros}")
            print(f"RETURNING HEIGHT: {new_height}(z)")
            print()

        return new_height


    def __del__(self):
        # Clean up DMA channels
        self.dma_row_read.close()
        self.dma_color_addr.close()
        self.dma_pixel_out.close()
        self.dma_h_scale.close()
        self.dma_row_start.close()
        self.dma_row_size.close()
        self.dma_v_scale.close()
