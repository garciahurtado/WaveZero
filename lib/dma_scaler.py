import sys

import time

import math
import uctypes

import rp2
from machine import Pin, mem32
from rp2 import DMA, PIO, const

from framebuf import FrameBuffer
from profiler import Profiler as prof
from dump_object import dump_object
from images.indexed_image import Image
from uctypes import addressof
from array import array
import utime
from utils import aligned_buffer

# 0x080 CH2_READ_ADDR
# 0x084 CH2_WRITE_ADDR
# 0x088 CH2_TRANS_COUNT
# 0x08c CH2_CTRL_TRIG
# 0x090 CH2_AL1_CTRL
# 0x094 CH2_AL1_READ_ADDR
CH0_DBG_TCR = 0x804


CH3_AL3_TRANS_COUNT = 0x0f8
CH3_AL1_TRANS_COUNT_TRIG = 0x0dc

CH2_AL1_TRANS_COUNT_TRIG=0x09c
CH4_READ_ADDR=0x100
CH4_WRITE_ADDR=0x104
CH4_TRANS_COUNT=0x108
CH4_CTRL_TRIG=0x10c
CH4_AL1_CTRL=0x110
CH4_AL1_READ_ADDR=0x114
CH4_AL1_WRITE_ADDR=0x118
CH4_AL1_TRANS_COUNT_TRIG=0x11c
CH4_AL2_CTRL=0x120
CH4_AL2_TRANS_COUNT=0x124
CH4_AL2_READ_ADDR=0x128
CH4_AL2_WRITE_ADDR_TRIG=0x12c

CH5_READ_ADDR=0x140
CH5_WRITE_ADDR=0x144
CH5_TRANS_COUNT=0x148
CH5_CTRL_TRIG=0x14c
CH5_AL1_CTRL=0x150
CH5_AL1_READ_ADDR=0x154
CH5_AL1_WRITE_ADDR=0x158
CH5_AL1_TRANS_COUNT_TRIG=0x15c
CH5_AL2_CTRL=0x160
CH5_AL2_TRANS_COUNT=0x164
CH5_AL2_READ_ADDR=0x168
CH5_AL3_READ_ADDR_TRIG = 0x17c

DMA_BASE   = const(0x50000000)
DMA_BASE_1 = const(0x50000040)
DMA_BASE_2 = const(0x50000080)
DMA_BASE_3 = const(0x500000C0)
DMA_BASE_4 = const(0x50000100)
DMA_BASE_5 = const(0x50000140)
DMA_BASE_6 = const(0x50000180)
DMA_BASE_7 = const(0x500001C0)
DMA_BASE_8 = const(0x50000200)

DMA_READ_ADDR = 0x000
DMA_READ_ADDR_AL1 = 0x014
DMA_WRITE_ADDR = 0x004
DMA_TRANS_COUNT_TRIG = 0x01c
DMA_WRITE_ADDR_TRIG = 0x02C
DMA_DBG_TCR = 0x804

PIO0_BASE = 0x50200000
PIO1_BASE = 0x50300000
# PIO1_TX = PIO1_BASE + 0x010
# PIO1_RX = PIO1_BASE + 0x020
#
# DREQ_PIO1_TX0 = 8
# DREQ_PIO1_RX0 = 12

PIO1_TX0 = PIO1_BASE + 0x010
PIO1_RX0 = PIO1_BASE + 0x020

PIO1_TX1 = PIO1_BASE + 0x014
PIO1_RX1 = PIO1_BASE + 0x024

FDEBUG = PIO1_BASE + 0x008

DREQ_PIO1_TX0 = 8
DREQ_PIO1_RX0 = 12

DREQ_PIO1_TX1 = 9
DREQ_PIO1_RX1 = 13

PIO_FSTAT = 0x004
PIO_FDEBUG = 0x008
PIO_INST_ADDR = 0x0d8

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

    debug = True
    debug_buffer_enable = False

    dma_row_read = None
    read_complete = False

    channel_names = [
        'row_read',
        'pixel_read',
        'palette',
        'pixel_out',
        'palette_rst',
        'row_size',
        'row_start',
    ]


    @rp2.asm_pio(
        # sideset_init=PIO.OUT_LOW,
        in_shiftdir=PIO.SHIFT_LEFT
    )
    def pixel_demux():
        pull()              [4]       # Pull 32 bits (4 bytes), set side pin to 0, wait 2 cycles
        set(x, 7)           [4]       # Set up loop counter (4 iterations, 0-7)

        label("loop")
        # set(y, null)        [4]
        out(y, 4)           [4]       # pull 4 bits from OSR
        in_(y, 32)          [4]       # spit them out as padded bytes
        push()              [4]

        nop()               [4]
        nop()               [4]

        jmp(x_dec, "loop")  [4]        # Decrement counter and loop if not zero

    """
        @rp2.asm_pio(
            sideset_init=PIO.OUT_LOW,
            in_shiftdir=PIO.SHIFT_LEFT,
        )
        def row_start_old():
            set(x, 0)           .side(0)    [2]
            pull()              #.side(1)    [4]
            out(y, 32)          #.side(1)    [4] # the first 4 bytes are saved
    
            # jmp("skip_start")
    
            wrap_target()
            pull()                  .side(0)
            out(x, 32)              #.side(1)[4]
    
            label("skip_start")
    
            label("y++")
            jmp(y_dec, "noop")      [4] # Subtract 1, skip the jump, then apply one's complement at the end, so is like a +1
            label("noop")
    
            mov(y, ~y)          .side(0)[4] # ones complement, so now we've subtracted from Y above
    
            jmp(x_dec, "y++")       [4]
    
            in_(y, 32)            .side(0)  [2] # push out the whole 4 byte addr of the start of the next row
            push()                          [2]
    """

    @rp2.asm_pio(
        in_shiftdir=PIO.SHIFT_LEFT,
    )
    def row_start():
        pull()
        mov(x, ~osr)

        wrap_target()
        pull()
        mov(y, osr)
        jmp("test")
                                    # this loop is equivalent to the following C code:
        label("incr")               # while (y--)
        jmp(x_dec, "test")          #     x--
                                    # This has the effect of subtracting y from x, eventually.
        label("test")
        jmp(y_dec, "incr")
        mov(isr, ~x)
        push

    dma_pixel_read = None
    dma_palette = None
    dma_pixel_out = None

    def init_pio(self):
        # Set up the PIO state machines
        # freq = 125 * 1000 * 1000
        freq = 2 * 1000

        """ Pixel demuxer / index reader """

        sm_id = 4 # 1st SM in PIO1
        sm_indices = rp2.StateMachine(sm_id)

        sm_indices.init(
            self.pixel_demux,
            freq=freq,
            # sideset_base=Pin(25),
        )

        self.sm_indices = sm_indices

        """ Row start address generator state machine """

        sm_id = 5  # 2nd SM in PIO1
        sm_row_start = rp2.StateMachine(sm_id)

        sm_row_start.init(
            self.row_start,
            freq=freq,
            sideset_base=Pin(22),
        )

        self.sm_row_start = sm_row_start

    def __init__(self, display, palette_size, channel2, channel3, channel4, channel5, channel6, channel7, channel8):

        """ Init static data buffers for the DMA channels """
        num_rows = 0  # Number of rows (in pixels) of the image being shown
        num_rows_buff = aligned_buffer(4, 4)
        self.num_rows_buff = array("L", num_rows_buff)

        row_size_buff = aligned_buffer(4, 4)
        self.row_size = array("L", row_size_buff)
        self.row_size[0] = display.width
        # row_size_bytes = (row_size).to_bytes(4, 'little')
        # row_size_buff = row_size_bytes
        self.row_size_buff = row_size_buff

        self.display = display
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
        self.color_addr_list = None

        self.read_complete = False

        debug_bytes = array("B", [0] * 256)
        self.debug_bytes = debug_bytes

        num_colors = 16

        palette_buffer = aligned_buffer(num_colors, 4)
        for i, color in enumerate([0x0011, 0xFFFF, 0x00FF, 0xFF00, 0x00FF, 0xF0A0, 0xA0A0, 0x0FFF]):
            palette_buffer[i] = color

        self.palette_buffer = array("H", palette_buffer)
        self.palette_buffer_addr = addressof(palette_buffer)

        color_addr_list_bytes = aligned_buffer(num_colors*4, 4)
        self.color_addr_list_bytes = color_addr_list_bytes
        self.color_addr_list = array("L", color_addr_list_bytes)

        for i, color_addr in enumerate(self.color_addr_list):
            self.color_addr_list[i] = self.palette_buffer_addr + (i*4)

        # for i in range(num_colors):
        #     addr = self.palette_buffer_addr + (i * 2)
        #     if debug:
        #         print(f"Saving new ADDR into COLORS ADDRS: {addr:08x}")
        #     self.color_addr_list[i] = addr

        rst_addr = uctypes.addressof(self.color_addr_list)
        self.rst_addr = rst_addr


        # PTR to new location with palette address, so we can pass it indirectly
        rst_addr_ptr_buf = aligned_buffer(4, 4)

        rst_addr_ptr = array("L", rst_addr_ptr_buf)

        rst_addr_ptr[0] = int(rst_addr)
        self.rst_addr_ptr = rst_addr_ptr
        self.rst_addr_ptr_buf = rst_addr_ptr_buf

        print()
        print(f"PALETTE RESTORE addr: {self.rst_addr:08x}")
        print(f"PALETTE RESTORE BUFF addr: {addressof(rst_addr_ptr):08x}")
        print(f"PALETTE RESTORE BUFF addr contents: {mem32[addressof(rst_addr_ptr)]:08x}")

        """ ----------- CONFIGURE PALETTE --------------------------"""

        if self.debug:
            # print()
            # print(f"Restore ADDR ARRAY: {restore_addr_arr:08x}")
            # print(f"Restore ADDR ARRAY CONTENTS: {mem32[restore_addr_arr]:08x}")
            # print()

            print(f"PALETTE COLORS ADDRESSES (size {palette_size})")
            print(f"START: {addressof(self.color_addr_list_bytes):08x} ")

        # for i in range(palette_size // 4):
        #     addr = uctypes.addressof(self.color_addr_list) + (i * 4)
        #     cont = mem32[addr]
        #     print(f"ADDR: {cont:08x}") #-{value2:02x}-{value3:02x}-{value4:02x}")

        print()

        self.init_pio()
        print(f"Screen dimensions: {self.screen_width}x{self.screen_height}")

        # self.ch_names = [DMA_BASE_2, DMA_BASE_3, DMA_BASE_4, DMA_BASE_5, DMA_BASE_6, DMA_BASE_7, DMA_BASE_8]

        self.ch_names = self.channel_names
        self.channels = [
            self.dma_row_read, self.dma_pixel_read, self.dma_palette,
            self.dma_pixel_out, self.dma_palette_rst, self.dma_row_size,
            self.dma_row_start]

        print(f"CALLING INIT_DMA with color ADDR list @ 0x{uctypes.addressof(color_addr_list_bytes):08x}")
        for color_addr in self.color_addr_list:
            print(f"- {color_addr:08x})")

        mv = memoryview(color_addr_list_bytes)
        self.init_dma(mv[0:1])


    def dma_handler(self, irq):
        print()
        print("~~~~@@ << DMA IRQ Was handled >> @@~~~~")
        print(irq.channel)
        print()
        # self.read_complete = True

    def dma_handler_debug(self, irq):
        print("  >>>> DMA TRANSFER <<<< complete for: #", end='')
        print(irq.channel)

    def pio_handler(self, event):
        """ Handle an IRQ from a SM"""
        print()
        print("+++ A PIO IRQ OCCURRED ++++")
        print()

    def init_dma(self, color_addr_start):
        """ Configure and initialize the DMA channels general settings (once only) """

        # self.total_width[0] = int(self.display.width*2)


        """ Image Read DMA channel - CH #2 - (feeds SM) --------------------------------------- """
        dma_row_read_ctrl = self.dma_row_read.pack_ctrl(
            size=2,
            inc_read=True,
            inc_write=False,
            treq_sel=DREQ_PIO1_TX0,
            chain_to=self.dma_row_size.channel,
            irq_quiet=False,
            # bswap=True
        )
        self.dma_row_read.config(
            count=0,            # TBD: pixels per row // 8
            read=0,             # TBD: memory address of the first pixel of the byte buffer of the image
            write=PIO1_TX0,
            ctrl=dma_row_read_ctrl,
        )
        self.dma_row_read.irq(handler=self.dma_handler)

        """ Pixel reader DMA channel - CH #3 - (post SM) ---------------------------- """
        if self.debug_buffer_enable:
            inc_write=True
        else:
            inc_write=False

        dma_pixel_read_ctrl = self.dma_pixel_read.pack_ctrl(
            size=2,
            inc_read=False,
            inc_write=inc_write,
            treq_sel=DREQ_PIO1_RX0,
        )

        if self.debug_buffer_enable:
            write_dest = self.debug_bytes
        else:
            write_dest = DMA_BASE_4 + DMA_TRANS_COUNT_TRIG

        self.dma_pixel_read.config(
            count=1,
            read=PIO1_RX0,
            write=write_dest,
            ctrl=dma_pixel_read_ctrl,
        )

        """ Palette DMA channel - CH #4 - --------------------------------------- """

        dma_palette_ctrl = self.dma_palette.pack_ctrl(
            size=2,  # 4 bytes per transfer \
            inc_read=True,
            inc_write=False,
            chain_to=self.dma_pixel_out.channel,
            ring_sel=True,
            ring_size=2,
            irq_quiet=False

        )
        self.dma_palette.config(
            count=0,
            read=self.color_addr_list_bytes,
            write=DMA_BASE_5 + DMA_READ_ADDR_AL1,
            # write=0,
            ctrl=dma_palette_ctrl,
        )

        """ Pixel out DMA channel - CH #5 --------------------- """
        dma_pixel_out_ctrl = self.dma_pixel_out.pack_ctrl(
            size=1,  # 16bit pixels
            inc_read=False,
            inc_write=True,
            chain_to=self.dma_palette_rst.channel,
        )

        self.dma_pixel_out.config(
            count=1, # In the future, this can be used to scale out (stretch) pixels for sprite scaling
            read=0,
            write=0, # TBD
            ctrl=dma_pixel_out_ctrl
        )

        """ palette ch ctrl DMA channel - CH #6 - Reconfigures palette read addr ------------------- """
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

        """ Row Size DMA channel - CH #7 - Resends the row size to PIO #2 ------------------- """
        dma_row_size_ctrl = self.dma_row_size.pack_ctrl(
            size=2,
            inc_read=False,
            inc_write=False,
            treq_sel=DREQ_PIO1_TX1,
            # chain_to=self.dma_pixel_read.channel,
            chain_to=self.dma_row_read.channel,
            # chain_to=self.dma_start_row.channel,
            bswap=False
        )
        self.dma_row_size.config(
            count=1,
            # read=0,  # TBD: pointer to row size int addr in RAM
            read=self.row_size_buff,
            write=PIO1_TX1,
            # write=self.dma_pixel_out.channel,
            ctrl=dma_row_size_ctrl,
        )

        """ Row Start DMA channel - CH #8 - Reloads the write reg of pixel_out to the start of the next row ------- """
        # if self.debug_buffer_enable:
        #     write = self.debug_bytes
        #     inc_write = True
        # else:
        #     write = DMA_BASE_5 + DMA_WRITE_ADDR
        #     inc_write = False

        write = DMA_BASE_5 + DMA_WRITE_ADDR
        inc_write = False

        dma_start_row_ctrl = self.dma_row_start.pack_ctrl(
            size=2,
            inc_read=False,
            inc_write=inc_write,
            treq_sel=DREQ_PIO1_RX1,
            # chain_to=self.dma_row_read.channel,
            # chain_to=self.dma_pixel_read.channel,
        )
        self.dma_row_start.config(
            count=1, # TBD: number of rows in image (height)
            read=PIO1_RX1,
            write=write,
            ctrl=dma_start_row_ctrl,
            trigger=True,
        )

    def config_dma(self, image, x, y, width, height):
        display = self.display
        num_pixels = width * height

        # write_addr = self.display.write_addr + ((y * self.screen_width) + x) * self.bytes_per_pixel
        write_addr = display.write_addr
        write_offset = ((y * display.width) + x) * 2 # since the display is 16 bit, we multiply x 2
        write_addr += write_offset
        #
        # print(f"DRAWING AT {x},{y} ({width}x{height})")
        # print(f"OFFSET: {write_offset}")
        # print(f"READING {num_pixels} PIXELS in {len(image.pixel_bytes)} BYTES")
        """ Update the configuration of the DMA channels to get them ready for a new (single frame) image display"""
        # num_pixels = 64 if self.debug_buffer_enable else num_pixels

        if self.debug_buffer_enable:
            num_rows = 1
            num_pixels_per_row = 16
            num_bytes_per_row = math.ceil(num_pixels_per_row / 2)
            num_words_per_row = math.ceil(num_bytes_per_row / 4)
        else:
            num_rows = height
            num_pixels_per_row = width
            num_bytes_per_row = math.ceil(num_pixels_per_row / 2)
            num_words_per_row = math.ceil(num_bytes_per_row / 4)

        self.num_rows_buff[0] = num_rows

        print("DISPLAY & MEM DETAILS:")
        print("------------------------")
        print(f"\twidth: {display.width}px")
        print(f"\theight: {display.height}px")
        print(f"\tnum_rows: {num_rows}")
        print(f"\tnum_bytes_per_row: {num_bytes_per_row}")
        print(f"\tnum_words_per_row: {num_words_per_row}")
        print(f"\tdisplay_out_addr: 0x{self.display.write_addr:08x}")
        print(f"\timg_read_addr: 0x{addressof(image.pixel_bytes):08x}")
        print(f"\tpalette_addr: 0x{addressof(self.color_addr_list_bytes):08x}")
        print(f"\tpalette_addr_ptr: 0x{addressof(self.rst_addr_ptr):08x}")
        print(f"\trow_size: 0x{self.row_size[0]:08x}")
        print(f"\trow_size_addr: 0x{addressof(self.row_size_buff):08x}")

        """ ----------- Set variable image configuration on the DMA channels -------------- """

        self.dma_row_read.read = image.pixel_bytes              # CH2
        # self.dma_row_read.count = math.ceil(width)          # CH2
        self.dma_row_read.count = (width * 2)        # CH2
        self.dma_pixel_read.count = 1                           # CH3
        self.dma_pixel_out.read = self.palette_buffer                    # CH5
        self.dma_pixel_out.write = write_addr                   # CH5
        self.dma_pixel_out.write = write_addr                   # CH5
        self.dma_palette.read = self.color_addr_list      # CH4
        self.dma_palette_rst.read = self.rst_addr_ptr           # CH6 -> wrong
        self.dma_row_size.read = self.row_size_buff             # CH7

        self.sm_row_start.put(write_addr) # prime it

    def show(self, image: Image, x, y, width, height, debug=True):
        print("==== PIXELBYTES SIZE ====")
        # print(f"LEN: {len(image.pixel_bytes)}")
        self.read_complete = False

        prof.start_profile('scaler.setup_dma')
        self.config_dma(image, x, y, width, height)
        prof.end_profile('scaler.setup_dma')

        write_offset = ((y * self.display.width) + x) * 2
        self.dma_pixel_out.write = self.display.write_addr + write_offset

        # for ch_num, _ in self.channel_names.items():
        #     idx = int(ch_num)
        #     ch = self.channels[idx]
        #     ch_alias = self.channel_names[ch_num]
        #     self.debug_dma(ch, ch_alias, 'before_start')


        for i in range(2, 9):
            idx = i - 2
            ch = self.channels[idx]
            ch_alias = self.channel_names[idx]
            ch_alias = ch_alias.upper()
            self.debug_dma(ch, ch_alias, 'before_start', idx+2)
            self.debug_pio_status()
            print("- - - - - - - - - - - - - - - - - - - - - ")
            self.debug_register()

        # Start the DMA transfer chain
        addr = int(addressof(image.pixel_bytes))
        addr = ~addr
        self.sm_row_start.put(addr)

        # SM
        self.sm_row_start.active(1)
        self.sm_indices.active(1)

        self.dma_row_read.active(1)
        self.dma_pixel_read.active(1)
        # self.dma_palette.active(1)

        # self.dma_row_start.active(1)
        # self.dma_row_size.active(1)
        # self.dma_palette_rst.active(1)

        """ As far as DMA goes, active and busy are the same thing """
        while (not self.read_complete):
            if debug:
                print("=====================================================")
                print(f"SM0 TX FIFO: {self.sm_indices.tx_fifo()}")
                print(f"SM0 RX FIFO: {self.sm_indices.rx_fifo()}")
                print("=====================================================")
                print(f"SM1 TX FIFO: {self.sm_row_start.tx_fifo()}")
                print(f"SM1 RX FIFO: {self.sm_row_start.rx_fifo()}")
                print("=====================================================")

                for i in range(2, 9):
                    idx = i - 2
                    ch = self.channels[idx]
                    ch_alias = self.channel_names[idx]
                    ch_alias = ch_alias.upper()
                    self.debug_dma(ch, ch_alias, 'in_loop', idx+2)
                    self.debug_pio_status()
                    print("- - - - - - - - - - - - - - - - - - - - - ")
                    self.debug_register()

            if self.debug_buffer_enable:
                print("----------------------------------------------")
                print("DEBUG BUFFER:")
                self.debug_buffer(self.debug_bytes)

            print(".loop")

            pass

        print("<<<-------- FINISHED READING IMAGE ---------->>>")

        if debug:
            for i in range(2, 9):
                idx = i - 2
                ch = self.channels[idx]
                ch_alias = self.channel_names[idx]
                ch_alias = ch_alias.upper()
                self.debug_dma(ch, ch_alias, 'post_dma', idx+2)
                self.debug_pio_status()
                print("- - - - - - - - - - - - - - - - - - - - - ")
                self.debug_register()

        self.sm_indices.active(0)
        self.sm_row_start.active(0)
        self.dma_row_read.active(0)
        self.dma_palette_rst.active(0)


    def status_to_bytes(self, status_int):
        status_int = status_int.to_bytes(4, 'big')
        status = [status_int[0], status_int[1], status_int[2], status_int[3]]
        return status

    def debug_pio_status(self):
        # status = self.status_to_bytes(mem32[addr])
        # print(f"DMA {num} STATUS: 0x{mem32[addr]:08x}")
        # print(" 3          2          1          0")
        # print("10987654-32109876-54321098-76543210")
        # print(f"{status[0]:08b}-{status[1]:08b}-{status[2]:08b}-{status[3]:08b}")
        print()

        inst_code = mem32[PIO1_BASE+PIO_INST_ADDR]
        self.read_pio_opcode(inst_code)

    def debug_register(self):
        deb1 = mem32[FDEBUG] >> 24
        deb2 = (mem32[FDEBUG] >> 16) & 0xFF
        deb3 = (mem32[FDEBUG] >> 8) & 0xFF
        deb4 = mem32[FDEBUG] & 0xFF
        print( "              TXSTALL    TXOVER     RXUNDER    RXSTALL")
        print(f"DEBUG REG >>> {deb1:08b} - {deb2:08b} - {deb3:08b} - {deb4:08b} <<<")

    def debug_dma(self, dma, alias, label, index):
        ctrl = dma.unpack_ctrl(dma.registers[3])
        DMA_NAME = f"DMA_BASE_{index}"
        DMA_ADDR = globals()[DMA_NAME]

        dbg_tcr = mem32[DMA_ADDR + DMA_DBG_TCR]

        active_txt = 'ACTIVE' if dma.active() else 'INACTIVE'
        print()
        print(f"CH '{alias}' (#{dma.channel}) | ({active_txt}) | ({label}):")
        print("---------------------------------------------------")
        print(f". ........ {dma.registers[0]:08x} R \t........ {dma.registers[9]:08x} TX (current)")
        print(f". ........ {dma.registers[1]:08x} W \t........ {dbg_tcr:08x} TCR (next)")
        print(f". ........ {dma.registers[3]:08x} CTRL")
        print(f"*. CTRL UNPACKED |")
        print(f"                 v")
        for idx1, idx2 in zip(range(0, len(ctrl), 2), range(1, len(ctrl), 2)):
            # rangerange(0, len(my_dict), 2):
            keys = list(ctrl.keys())
            key1 = keys[idx1]
            key2 = keys[idx2]
            value1 = ctrl[key1]
            value2 = ctrl[key2]
            print(f".{key1:_<12} {value1:02x} \t\t .{key2:_<12} {value2:02x}")

        # for idx, reg in enumerate(dma.registers):
        #     print(f"{idx}- {reg:032x}")


    def debug_buffer(self, data_bytes):
        # print(f"Framebuf addr: {buffer_addr:16x} / len: {len(data_bytes)}")
        print(f"Debug Buffer Contents: ")
        print()

        rows=4
        cols=16

        for r in range(0, rows):
            words = []
            for c in range(0, cols):
                idx = (r * cols) + c
                words.append(f"{data_bytes[idx]:02x}")

            print("-".join(words))

        print()

    def read_pio_opcode(self, instr):
        opcode = (instr & 0xE000) >> 13

        opcodes = [
            "JMP", "WAIT", "IN", "OUT", "PUSH/PULL", "MOV", "IRQ", "SET"
        ]

        if opcode < len(opcodes):
            print(f"Instruction: {opcodes[opcode]}")

            if opcode == 0:  # JMP
                condition = (instr >> 5) & 0x7
                address = instr & 0x1F
                conditions = ["ALWAYS", "!X", "X--", "!Y", "Y--", "X!=Y", "PIN", "!OSRE"]
                print(f"Condition: {conditions[condition]}, Address: {address}")
            elif opcode == 4:  # PUSH/PULL
                if instr & 0x80:
                    print("PULL instruction")
                else:
                    print("PUSH instruction")
                if instr & 0x60:  # Check if blocking
                    print("Blocking")
                else:
                    print("Non-blocking")
        else:
            print("Unknown instruction")

    def __del__(self):
        # Clean up DMA channels
        self.dma_row_read.close()
        self.dma_pixel_read.close()
        self.dma_palette.close()
        self.dma_pixel_out.close()
