import math

import sys

import random
import utime

from scaler.dma_scaler_debug import ScalerDebugger
from scaler.dma_scaler_pio import *
from uctypes import addressof

from machine import Pin, mem32
import time
import uctypes

import rp2
from rp2 import DMA, PIO

from profiler import Profiler as prof
from images.indexed_image import Image
from array import array

from scaler.dma_scaler_const import *
from utils import *

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
    h_patterns_int = []
    v_patterns_up_int = []
    v_patterns_down_int = []

    h_patterns_ptr = []
    h_pattern_buf_all = []

    v_patterns_up_ptr = []
    scale_index = 0
    last_scale_shift = 0 #
    scale_shift_freq = 50 # every X ms, scale shifts one step
    bytes_per_pixel = 2
    sm_palette_idx = None
    sm_row_start = None
    row_tx_count = 0

    debug = False
    debug_buffer_enable = False
    dbg: ScalerDebugger = None

    dma_row_read = None
    read_finished = False

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

    def init_pio(self):
        # Set up the PIO state machines
        # freq = 125 * 1000 * 1000
        freq = 2 * 1000 * 1000
        # freq = 1000 * 1000

        """ SM0: Pixel demuxer / palette reader """
        sm_indices = self.sm_palette_idx
        sm_indices.init(
            read_palette,
            freq=freq,
        )

        """ SM1:  Row start address generator (write) """
        sm_row_start = self.sm_row_start
        sm_row_start.init(
            row_start,
            freq=freq,
        )

        """ SM2:  Row start address generator (read) """
        sm_vert_scale = self.sm_vert_scale
        sm_vert_scale.init(
            row_start,
            freq=freq,
        )

        self.sm_palette_idx.active(1)
        self.sm_row_start.active(1)
        self.sm_vert_scale.active(1)

    def __init__(self, display, palette_size,
                 channel2, channel3, channel4, channel5, channel6, channel7, channel8):
        self.write_addr_base = display.write_addr

        """ DMA Channels"""
        self.dma_row_read = channel2
        self.dma_color_addr = channel3
        self.dma_pixel_out = channel4
        self.dma_h_scale = channel5
        self.dma_row_size = channel6
        self.dma_row_start = channel7
        self.dma_v_scale = channel8

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

        row_size_buff = bytearray(4)
        self.row_size = array("L", row_size_buff)
        self.row_size[0] = int(display.width * 2) - 1 # 0x0C0

        print("~ CONTENTS OF ROW_SIZE ARRAY ~")
        print(f"0x{self.row_size[0]:08x}")

        print(f"SETTING ROW_SIZE TO {display.width * 2} =  {self.row_size[0]}")

        self.display = display
        self.write_start_addr = addressof(self.display.write_framebuf)

        self.screen_width = self.display.width
        self.screen_height = self.display.height
        self.palette_size = palette_size

        """ SM0: Pixel demuxer / index reader """
        self.sm_palette_idx = rp2.StateMachine(4)               # 1st SM in PIO1

        """ SM1:  Row start address generator """
        self.sm_row_start = rp2.StateMachine(5)             # 2nd SM in PIO1

        """ SM2:  Row start address generator (read) """
        self.sm_vert_scale = rp2.StateMachine(6)             # 3nd SM in PIO1


        """ Debug Buffer """
        if self.debug:
            self.dbg = ScalerDebugger(self.sm_palette_idx, self.sm_row_start, self.sm_vert_scale)
            self.dbg.channel_names = self.channel_names
            self.dbg.channels = self.channels
            self.debug_bytes = self.dbg.get_debug_bytes()

        """ 
        Scaling Patterns ---------------------------------- 
        These buffers will be used to double horizontal pixels at set intervals, in order to implement upscaling 
        The data will be sent to the pixel_out DMA count field. from another channel with a ring buffer of 
        size = len(pattern)
        """
        self.pattern_size = pattern_size = 8 # num elements in one pattern

        h_patterns_int = [
            [1, 1, 1, 1, 1, 1, 1, 1], # 0s dont work at the moment, nor the last 4 bits :(
            [1, 1, 1, 1, 2, 1, 1, 1],       # 12.5%
            [1, 1, 2, 1, 1, 1, 2, 1],       # 25%
            [1, 1, 2, 1, 1, 2, 1, 2],       # 37.5%
            [1, 2, 1, 2, 1, 2, 1, 2],       # 50%
            [2, 1, 2, 2, 1, 2, 1, 2],       # 62.5%
            [2, 1, 2, 2, 2, 1, 2, 2],       # 75%
            [2, 2, 2, 2, 1, 2, 2, 2],       # 87.5%
            [2, 2, 2, 2, 2, 2, 2, 2],        # 100%
            # [2, 2, 2, 2, 3, 2, 2, 2],       # 112.5%
            # [2, 2, 3, 2, 2, 2, 3, 2],       # 135%
            # [2, 2, 3, 2, 2, 3, 2, 3],       # 137.5%
            # [2, 3, 2, 3, 2, 3, 2, 3],       # 150%
            # [3, 2, 3, 3, 2, 3, 2, 3],       # 162.5%
            # [3, 2, 3, 3, 3, 2, 3, 3],       # 175%
            # [3, 3, 3, 3, 2, 3, 3, 3],       # 187.5%
            # [3, 3, 3, 3, 3, 3, 3, 3],       # 200%
            # [3, 3, 3, 3, 4, 3, 3, 3],       # 212.5%
            # [3, 3, 4, 3, 3, 3, 4, 3],       # 235%
            # [3, 3, 4, 3, 3, 4, 3, 4],       # 237.5%
            # [3, 4, 3, 4, 3, 4, 3, 4],       # 250%
            # [4, 3, 4, 4, 3, 4, 3, 4],       # 262.5%
            # [4, 3, 4, 4, 4, 3, 4, 4],       # 275%
            # [4, 4, 4, 4, 3, 4, 4, 4],       # 287.5%
            # [4, 4, 4, 4, 4, 4, 4, 4]        # 300%
        ]
        self.h_patterns_int = h_patterns_int

        """ Doubling a vert pattern value (row size) from 0xC0 to 0x0180 allows us to have a one-on / one-off type x2 pattern"""
        v_patterns_down_int = [
            [1, 1, 1, 1, 1, 1, 1, 1],
            [0, 0, 0, 0, 1, 0, 0, 0],  # 12.5%
            [0, 0, 1, 0, 0, 0, 1, 0],  # 25%
            [0, 0, 1, 0, 0, 1, 0, 1],  # 37.5%
            [0, 1, 0, 1, 0, 1, 0, 1],  # 50%
            [1, 0, 1, 1, 0, 1, 0, 1],  # 62.5%
            [1, 0, 1, 1, 1, 0, 1, 1],  # 75%
            [1, 1, 1, 1, 0, 1, 1, 1],  # 87.5%
            [1, 1, 1, 1, 1, 1, 1, 1],  # 100%
        ]
        self.v_patterns_down_int = v_patterns_down_int

        v_patterns_up_int = [
            [1, 1, 1, 1, 1, 1, 1, 1],
            [1, 1, 1, 1, 2, 1, 1, 1],  # 12.5%
            [1, 1, 2, 1, 1, 1, 2, 1],  # 25%
            [1, 1, 2, 1, 1, 2, 1, 2],  # 37.5%
            [1, 2, 1, 2, 1, 2, 1, 2],  # 50%
            [2, 1, 2, 2, 1, 2, 1, 2],  # 62.5%
            [2, 1, 2, 2, 2, 1, 2, 2],  # 75%
            [2, 2, 2, 2, 1, 2, 2, 2],  # 87.5%
            [2, 2, 2, 2, 2, 2, 2, 2],  # 100%
        ]
        self.v_patterns_up_int = v_patterns_up_int

        """ We need to turn these lists into basic arrays so that the pointers are easier to pass to DMA """
        self.h_patterns_ptr = array('L', [0x00000000] * len(h_patterns_int))
        self.v_patterns_down_ptr = array('L', [0x00000000] * len(v_patterns_down_int))
        self.v_patterns_up_ptr = array('L', [0x00000000] * len(v_patterns_up_int))


        # print("//// SCALING PATTERNS (horiz upscaling) \\\\\\\\")
        for i, scale_pattern in enumerate(h_patterns_int):
            h_pattern_buf = bytearray(pattern_size * 4)
            h_pattern = array('L', h_pattern_buf)

            for j, element in enumerate(scale_pattern):
                h_pattern[j] = int(element)

            # print(f"#{i} PATTERN - len: {len(scale_pattern)} 0x{addressof(h_pattern):08x}")

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
        for i, scale_pattern in enumerate(v_patterns_up_int):
            v_pattern_buf = bytearray(pattern_size * 4)
            v_pattern = array('L', v_pattern_buf)

            for j, value in enumerate(scale_pattern):
                v_pattern[j] = int(value)

            self.v_patterns_up_ptr[i] = addressof(v_pattern)
            # all_patterns.append(v_pattern)
            # all_buffers.append(v_pattern_buf)

        self.h_scale_ptr = self.h_patterns_ptr[0]
        self.v_scale_down_ptr = self.v_patterns_down_ptr[0]
        self.v_scale_up_ptr = self.v_patterns_up_ptr[0]

        print(f"INIT H PATTERN ADDR: 0x{self.h_scale_ptr:08x}")
        print(f"INIT V PATTERN ADDR: 0x{self.v_scale_down_ptr:08x}")

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
        self.stop_scaler()

        self.sm_palette_idx.restart() # restart() does NOT start the machine, only resets the PC and internal state/regs
        self.sm_row_start.restart()

        self.dma_pixel_out.count = 1
        self.write_start_addr = addressof(self.display.write_framebuf)


    def dma_handler_debug(self, irq):
        print("  >>>> DMA TRANSFER <<<< complete for: #", end='')
        print(irq.channel)


    def init_dma(self):
        """ Configure and initialize the DMA channels general settings (once only) """

        """ Image Read DMA channel - CH #2 - (feeds SM0) --------------------------------------- """

        dma_row_read_ctrl = self.dma_row_read.pack_ctrl(
            size=0, # 1 byte per tx
            inc_read=True,
            inc_write=False,
            treq_sel= DREQ_PIO1_TX0,
            chain_to=self.dma_row_size.channel,
            bswap=True,
        )
        self.dma_row_read.config(
            count=0,            # To be set later: img pixels per row // 2
            read=0,             # To be set later: memory address of the first pixel of the framebuffer of the sprite
            write=PIO1_TX0,
            ctrl=dma_row_read_ctrl,
        )

        """ Color address - CH #3- pass the resulting palette address to the pixel writer """

        dma_color_addr_ctrl = self.dma_color_addr.pack_ctrl(
            size=2,
            inc_read=False,
            inc_write=False,
            treq_sel=DREQ_PIO1_RX0,
            chain_to=self.dma_pixel_out.channel,
            irq_quiet=False
        )

        self.dma_color_addr.config(
            count=1,
            read=PIO1_RX0,
            write=DMA_BASE_4 + DMA_READ_ADDR_TRIG,
            ctrl=dma_color_addr_ctrl,
        )
        self.dma_color_addr.irq(handler=self.irq_img_end)

        """ Pixel out DMA channel - CH #4 --------------------- """
        dma_pixel_out_ctrl = self.dma_pixel_out.pack_ctrl(
            size=1,                 # output one pixel at a time (2 bytes)
            inc_read=False,
            inc_write=True,
            chain_to=self.dma_h_scale.channel,
        )

        self.dma_pixel_out.config(
            count=1,            # Increasing this above 1 will stretch pixels horizontally for sprite scaling
            read=0,
            write=0,            # To be set later
            ctrl=dma_pixel_out_ctrl,
        )

        """ Horizontal Upscale channel - CH #5 - uses a ring buffer t provide a pattern of pixel repetition for scaling """
        # if self.debug_buffer_enable:
        #     scale_write = self.debug_bytes
        #     scale_inc_write = True
        # else:
        scale_write = DMA_BASE_4 + DMA_TRANS_COUNT
        scale_inc_write = False

        dma_h_scale_ctrl = self.dma_h_scale.pack_ctrl(
            size=2,
            inc_read=True,
            inc_write=scale_inc_write,
            # chain_to=self.dma_color_addr.channel,
            ring_sel=0,
            ring_size=4, # 4 el pattern
        )

        self.dma_h_scale.config(
            count=1,
            read=self.h_scale_ptr,
            write=scale_write,
            ctrl=dma_h_scale_ctrl,
        )


        """ Row Size DMA channel - CH #6 - Sends the new row size to calculate another offset ------------------- """

        dma_row_size_ctrl = self.dma_row_size.pack_ctrl(
            size=2,
            inc_read=True,
            inc_write=False,
            treq_sel=DREQ_PIO1_TX1,
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

        """ Row Start DMA channel - CH #7 - Reloads the write reg of pixel_out to the start of the next row  """
        if self.debug_buffer_enable:
            row_s_write = self.debug_bytes
            row_s_inc_write = True
        else:
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

        """ Vert Scale DMA channel - CH #8 - Reconfigures the start addr of the read head, in order to implement
          vertical scaling."""

        dma_v_scale_ctrl = self.dma_v_scale.pack_ctrl(
            size=2,
            inc_read=True,
            inc_write=False,
            treq_sel=DREQ_PIO1_TX2,
            ring_sel=0,
            ring_size=4
        )
        self.dma_v_scale.config(
            count=0,
            read=0,
            write=PIO1_TX2,
            ctrl=dma_v_scale_ctrl,
        )

    def irq_img_end(self, irq_obj):
        if self.debug:
            print()
            print("<<<<<< IMG END IRQ - Triggered / Read Complete >>>>>>")
            print()
        self.read_finished = True

    def config_dma(self, image, x, y, width, height):
        # print(f"DMA: x:{x} y:{y} ")

        display = self.display
        num_pixels = width * height
        write_addr_base = self.write_addr_base

        write_addr = display.write_addr
        write_offset = (((y * display.width) + x) * 2) - 8  # since the display is 16 bit, we multiply x 2
        self.write_addr = write_addr_base + write_offset

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
        self.read_finished = False

        """ ----------- Set variable per-image configuration on all the DMA channels -------------- """
        hscale = sum(self.h_patterns_int[self.scale_index]) / self.pattern_size
        vscale = sum(self.v_patterns_down_int[0]) / self.pattern_size

        actual_width = int(width * hscale)
        actual_height = round(height * vscale)

        prof.start_profile('scaler.prep_img_vars')
        num_pixels = int(actual_width * actual_height)

        # row_tx_count = int(width + self.h_skew) # Adding / substracting can apply skew to the image
        row_tx_count = math.ceil(actual_width / (2 * hscale))
        prof.end_profile('scaler.prep_img_vars')

        if self.debug:
            print(f"IMAGE WIDTH (px): {width}")
            print(f"IMAGE HSCALE: {hscale:04f}")
            print(f"IMAGE SUM/SIZE: {sum(self.h_patterns_int[0])}/{self.pattern_size}")
            print(f"IMAGE ACTUAL WIDTH (px): {actual_width}")
            print(f"IMAGE HEIGHT (px): {height}")
            print(f"IMAGE VSCALE: {vscale:04f}")
            print(f"IMAGE ACTUAL HEIGHT (px): {actual_height}")
            print(f"TOTAL IMG PX: {num_pixels}")
            print(f"ROW TX COUNT (32bit): {row_tx_count}")
            print(f"SCALE IDX: {self.scale_index}")

        prof.start_profile('scaler.config_dma')
        self.config_dma(image, x, y, width, height)
        prof.end_profile('scaler.config_dma')

        # print(f"SCALER WRITING TO WRITE BUFF @:{self.write_addr_base:08x}")

        prof.start_profile('scaler.dma_init_values')
        self.dma_row_read.read = image.pixel_bytes_addr                 # CH2
        # self.dma_row_read.read = PIO1_RX2                 # CH2
        self.dma_row_read.count = row_tx_count                         #   for 1byte width
        self.dma_color_addr.count = image.width * image.height                    # CH3
        self.dma_pixel_out.read = self.palette_buffer                   # CH4
        self.dma_pixel_out.write = self.write_addr
        self.dma_pixel_out.count = 1                                    # We can set the horizontal scale here (upscaling)

        pattern_addr = self.h_patterns_ptr[self.scale_index]
        self.dma_h_scale.read = pattern_addr                              # CH5 -
        self.dma_row_size.read = self.v_scale_down_ptr                         # CH6 -
        self.dma_row_size.count = 1

        """ CH 8"""
        self.dma_v_scale.count = image.height
        self.dma_v_scale.read = self.v_patterns_up_ptr[0]

        prof.end_profile('scaler.dma_init_values')

        if self.debug:
            for idx in self.channel_names.keys():
                self.dbg.debug_dma_channel(idx, 'BEFORE_START')

        """ State Machine startup -----------------------"""
        prof.start_profile('scaler.start_pio')

        # sm.irq(lambda p: print(time.ticks_ms()))
        """ Prime color SM with first palette addr. """
        color_addr = addressof(image.palette_bytes)
        if self.debug:
            print(f"~~~ Priming SM0 with {color_addr:08x} ~~~")

        self.sm_palette_idx.put(color_addr)

        if self.debug:
            print(f"~~~ Priming SM1 (write) with addr:{self.write_addr:08x} and row size:{self.row_size[0]:08x} ~~~")
        """
        Prime row start SM with:
        1. Write framebuffer addr
        2. Row size (0xC0 = 192 bytes per row for write)
        """
        self.sm_row_start.put(self.write_addr)
        self.sm_row_start.put(self.row_size[0])  # 0xC0 for display width
        # self.sm_row_start.put(1)                 # 1st pattern

        if self.debug:
            print(f"~~~ Priming SM2 (read) with addr:{image.pixel_bytes_addr:08x} and row size:{width // 2:08x} ~~~")
        """
        Prime vertical scale SM with:
        1. Image data read addr
        2. Row size (width/2 for read since we're reading 2 pixels at a time)
        3. 1st pattern
        """
        # self.sm_vert_scale.put(image.pixel_bytes_addr)
        # self.sm_vert_scale.put(width // 2)  # Input width divided by 2 since we read 2 pixels at once
        # self.sm_vert_scale.put(1)
        #
        # if self.debug:
        #     print(f"~~~ Priming SM2 with {image.pixel_bytes_addr:08x} // {width // 2} // 1 ~~~")

        """ Start State Machines """
        self.sm_row_start.active(1)
        self.sm_palette_idx.active(1)
        # self.sm_vert_scale.active(1)

        prof.end_profile('scaler.start_pio')

        if self.debug:
            print("- Starting DMA channels -")

        """ DMA - We only need to kick off the channels that don't have any other means to get started (like chain_to)"""
        prof.start_profile('scaler.start_dma')

        # self.dma_pixel_out.active(1) # Omitting Avoids extra pixel on 1st row
        self.dma_color_addr.active(1)
        self.dma_row_read.active(1)

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
                    self.dbg.debug_dma_channel(idx, 'IN_LOOP')

            if self.debug_buffer_enable:
                print(self.dbg)
                print("----------------------------------------------")
                print("DEBUG BUFFER:")
                self.dbg.debug_buffer(self.debug_bytes)

        prof.end_profile('scaler.inner_loop')

        if self.debug:
            print("<<<<-------- FINISHED READING IMAGE ---------->>>>")

        self.update_scale()

    def stop_scaler(self):
        self.sm_palette_idx.active(0)
        self.sm_row_start.active(0)

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

        print()

    def update_scale(self):
        """ shift the scale"""
        max_idx = len(self.h_patterns_ptr) - 1

        diff = utime.ticks_diff(utime.ticks_ms(), self.last_scale_shift)

        if diff > self.scale_shift_freq:
            prof.start_profile('scaler.scale_shift')

            self.scale_index += (1 * self.scale_index_flip)

            if self.scale_index > max_idx:
                self.scale_index = max_idx
                self.scale_index_flip = self.scale_index_flip * -1

            if self.scale_index < 1:
                self.scale_index = 1
                self.scale_index_flip = self.scale_index_flip * -1

            if self.debug:
                print(f"=== Shifted scale to: {self.scale_index}")

            self.last_scale_shift = utime.ticks_ms()

            prof.end_profile('scaler.scale_shift')


    def __del__(self):
        # Clean up DMA channels
        self.dma_row_read.close()
        self.dma_color_addr.close()
        self.dma_pixel_out.close()
        self.dma_h_scale.close()
        self.dma_row_start.close()
        self.dma_row_size.close()
        self.dma_v_scale.close()
