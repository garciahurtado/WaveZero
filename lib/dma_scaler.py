import sys

import time
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

DMA_READ_ADDR = 0x000
DMA_READ_ADDR_AL1 = 0x014
DMA_WRITE_ADDR = 0x004
DMA_TRANS_COUNT_TRIG = 0x01c
DMA_WRITE_ADDR_TRIG = 0x02C

PIO0_BASE = 0x50200000
PIO1_BASE = 0x50300000
# PIO1_TX = PIO1_BASE + 0x010
# PIO1_RX = PIO1_BASE + 0x020
#
# DREQ_PIO1_TX0 = 8
# DREQ_PIO1_RX0 = 12

PIO1_TX = PIO1_BASE + 0x010
PIO1_RX = PIO1_BASE + 0x020
FDEBUG =  PIO1_BASE + 0x008

# DREQ_PIO0_TX0 = 8
# DREQ_PIO0_RX0 = 12

DREQ_PIO1_TX0 = 8
DREQ_PIO1_RX0 = 12

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
    sm = None
    debug = False
    debug_buffer_enable =False

    dma_img_read = None
    read_complete = False

    @rp2.asm_pio(
        sideset_init=PIO.OUT_LOW,
        in_shiftdir=PIO.SHIFT_LEFT,
    )
    def pixel_demux():
        pull()              .side(0)[4]       # Pull 32 bits (4 bytes), set side pin to 0, wait 2 cycles
        set(x, 7)           .side(1)[4]       # Set up loop counter (8 iterations, 0-7)

        label("loop")
        set(y, null)                [4]
        out(y, 4)           .side(0)[4]       # pull 4 bits from OSR
        in_(y, 32)                             # spit them out as padded bytes
        push()

        jmp(x_dec, "loop")  .side(1)[4]        # Decrement counter and loop if not zero


    dma_pixel_read = None
    dma_palette = None
    dma_pixel_out = None

    def init_pio(self):
        # Set up the PIO state machine
        # freq = 125 * 1000 * 1000
        freq = 3 * 1000
        sm_id = 4 # 1st SM in PIO1
        sm = rp2.StateMachine(sm_id)

        sm.init(
            self.pixel_demux,
            freq=freq,
            sideset_base=Pin(25),
        )

        # self.sm_debug(sm)
        # sm.irq(self.pio_handler, trigger=0, hard=True)
        self.sm = sm

    def __init__(self, display, palette_size, channel2, channel3, channel4, channel5, channel6, channel7,
                 debug=True, debug_buffer_enable=False):

        self.display = display
        self.screen_width = self.display.width
        self.screen_height = self.display.height
        self.palette_size = palette_size

        self.debug = debug
        self.debug_buffer_enable = debug_buffer_enable

        """ DMA Channels"""
        self.dma_img_read = channel2
        self.dma_pixel_read = channel3
        self.dma_pixel_read_rst = channel7
        self.dma_palette = channel4
        self.dma_palette_ctrl = channel6
        self.dma_pixel_out = channel5
        self.color_addr_list = None

        self.read_complete = False

        debug_bytes = array("B", [0] * 256)
        self.debug_bytes = debug_bytes

        num_colors = 8

        palette_buffer = aligned_buffer(num_colors * 2, 4)
        self.palette_buffer = array("H", palette_buffer)
        self.palette_buffer_addr = addressof(palette_buffer)

        for i, color in enumerate([0x0000, 0xFFFF, 0x00FF, 0xFF00, 0xFF00, 0xFF00, 0xFF00, 0xFF00]):
            palette_buffer[i] = color

        color_addr_list_bytes = aligned_buffer(num_colors * 2, 4)
        self.color_addr_list_bytes = color_addr_list_bytes
        self.color_addr_list = array("L", color_addr_list_bytes)

        for i, color_addr in enumerate(self.color_addr_list):
            self.color_addr_list[i] = self.palette_buffer_addr + (i*4)

        # for i in range(num_colors):
        #     addr = self.palette_buffer_addr + (i * 2)
        #     if debug:
        #         print(f"Saving new ADDR into COLORS ADDRS: {addr:08x}")
        #     self.color_addr_list[i] = addr

        restore_addr = self.color_addr_list[0]
        self.restore_addr = uctypes.addressof(color_addr_list_bytes)


        # Container of containers
        restore_addr_arr_ptr_buf = aligned_buffer(4, 4)
        restore_addr_arr_ptr_ptr = array("L", restore_addr_arr_ptr_buf)
        self.restore_addr_arr_ptr_ptr = restore_addr_arr_ptr_ptr

        # original pointer
        restore_addr_buff = aligned_buffer(4, 4)
        restore_addr_arr = array("L", restore_addr_buff)
        restore_addr_arr[0] = restore_addr
        self.restore_addr_buff = restore_addr_buff

        restore_addr_arr_ptr = addressof(restore_addr_arr)
        self.restore_addr_arr_ptr = restore_addr_arr_ptr
        self.restore_addr_arr = restore_addr_arr

        restore_addr_arr_ptr_ptr[0] = uctypes.addressof(restore_addr_buff)
        self.restore_addr_arr_ptr_ptr = restore_addr_arr_ptr_ptr


        """ ----------- CONFIGURE PALETTE --------------------------"""

        if debug:
            # print()
            # print(f"Restore ADDR ARRAY: {restore_addr_arr:08x}")
            # print(f"Restore ADDR ARRAY CONTENTS: {mem32[restore_addr_arr]:08x}")
            # print()

            print(f"PALETTE COLORS ADDRESSES (size {palette_size})")
            print(f"START: {addressof(self.color_addr_list):08x} ")

        for i in range(palette_size // 4):
            addr = uctypes.addressof(self.color_addr_list) + (i * 4)
            cont = mem32[addr]
            print(f"ADDR: {cont:08x}") #-{value2:02x}-{value3:02x}-{value4:02x}")

        print()

        self.init_pio()
        print(f"Screen dimensions: {self.screen_width}x{self.screen_height}")

        self.ch_names = [DMA_BASE_2, DMA_BASE_3, DMA_BASE_4, DMA_BASE_5, DMA_BASE_6]
        self.channels = [self.dma_img_read, self.dma_pixel_read, self.dma_palette, self.dma_pixel_out, self.dma_palette_ctrl]

        print(f"CALLING INIT_DMA with color ADDR list @ 0x{uctypes.addressof(color_addr_list_bytes):08x}")
        for color_addr in self.color_addr_list:
            print(f"- {color_addr:08x})")

        mv = memoryview(color_addr_list_bytes)
        self.init_dma(mv[0:1])


    def dma_handler(self, irq):
        # print("IRQ Was handled")
        # print(irq.channel)
        self.read_complete = True

    def dma_handler_debug(self, irq):
        print("  >>>> DMA TRANSFER <<<< complete for: #", end='')
        print(irq.channel)

    def pio_handler(self, event):
        """ Handle an IRQ from a SM"""
        print()
        print("+++ A PIO IRQ OCCURRED ++++")
        print()


    def init_dma(self, color_addr_start):
        """ Configure and initialize the DMA channels for a new image """

        """ Image Read DMA channel - CH #2 - (feeds SM) --------------------------------------- """
        dma_img_read_ctrl = self.dma_img_read.pack_ctrl(
            size=2,
            inc_read=True,
            inc_write=False,
            treq_sel=DREQ_PIO1_TX0,
            chain_to=self.dma_pixel_read.channel,
        )
        self.dma_img_read.config(
            count=0, # TBD
            read=0, # TBD
            write=PIO1_TX,
            ctrl=dma_img_read_ctrl,
        )
        # self.dma_img_read.irq(handler=self.dma_handler)

        """ Pixel reader DMA channel - CH #3 - (post SM) ---------------------------- """
        if self.debug_buffer_enable:
            chain_to = self.dma_palette_ctrl.channel
            inc_write = True
        else:
            chain_to = self.dma_pixel_read.channel
            inc_write = False

        dma_pixel_read_ctrl = self.dma_pixel_read.pack_ctrl(
            size=2,
            inc_read=False,
            inc_write=inc_write,
            treq_sel=DREQ_PIO1_RX0,
            chain_to=chain_to,
            bswap=False,
            irq_quiet=False
        )

        if self.debug_buffer_enable:
            write_dest = self.debug_bytes
        else:
            write_dest = DMA_BASE_4 + DMA_TRANS_COUNT_TRIG

        self.dma_pixel_read.config(
            count=1,
            read=PIO1_RX,
            write=write_dest,
            ctrl=dma_pixel_read_ctrl,
        )
        self.dma_pixel_read.irq(handler=self.dma_handler)

        """ Palette DMA channel - CH #4 - --------------------------------------- """

        dma_palette_ctrl = self.dma_palette.pack_ctrl(
            size=2,  # 2 bytes per transfer \
            inc_read=True,
            inc_write=False,
            chain_to=self.dma_pixel_out.channel,
            bswap=False,
            high_pri=True
        )
        self.dma_palette.config(
            count=0,
            read=self.color_addr_list,
            write=DMA_BASE_5+DMA_READ_ADDR_AL1,
            # write=0,
            ctrl=dma_palette_ctrl,
        )

        """ Pixel out DMA channel - CH #5 --------------------- """
        dma_pixel_out_ctrl = self.dma_pixel_out.pack_ctrl(
            size=1,  # 16bit pixels
            inc_read=False,
            inc_write=True,
            chain_to=self.dma_palette_ctrl.channel,
        )

        self.dma_pixel_out.config(
            count=1,
            read=0,
            write=0, # TBD
            ctrl=dma_pixel_out_ctrl
        )

        """ palette ch ctrl DMA channel - CH #6 - Reconfigures palette read addr ------------------- """
        dma_palette_ctrl_ctrl = self.dma_palette_ctrl.pack_ctrl(
            size=2,
            inc_read=False,
            inc_write=False,
            chain_to=self.dma_pixel_read.channel,
            irq_quiet=False
        )
        self.dma_palette_ctrl.config(
            count=1,
            read=0, # TBD
            write=DMA_BASE_4 + DMA_READ_ADDR_AL1,
            ctrl=dma_palette_ctrl_ctrl,
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
        num_pixels = 64 if self.debug_buffer_enable else num_pixels

        self.dma_img_read.read = image.pixel_bytes          # CH2
        self.dma_img_read.count = num_pixels  // 8         # CH2
        self.dma_pixel_read.count = num_pixels      # CH3
        self.dma_pixel_out.write = write_addr               # CH5
        self.dma_palette.read = self.color_addr_list   # CH4
        self.dma_palette_ctrl.read = self.color_addr_list_bytes # CH6

    def show(self, image: Image, x, y, width, height, debug=True):
        print("==== PIXELBYTES SIZE ====")
        # print(f"LEN: {len(image.pixel_bytes)}")
        self.read_complete = False

        prof.start_profile('scaler.setup_dma')
        self.config_dma(image, x, y, width, height)
        prof.end_profile('scaler.setup_dma')

        for name, ch in zip(self.ch_names, self.channels):
            self.debug_dma(ch, name, 'before_start')
            self.debug_pio_status()
            print("- - - - - - - - - - - - - - - - - - - - - ")
            self.debug_register()

        # Start the DMA transfer chain
        self.sm.active(1)
        self.dma_img_read.active(1)
        self.dma_pixel_read.active(1)
        # self.dma_palette.active(1)
        # self.dma_palette_ctrl.active(1)

        """ As far as DMA goes, active and busy are the same thing """
        while (not self.read_complete):
            if debug:
                print("=====================================================")
                print(f"TX FIFO: {self.sm.tx_fifo()}")
                print(f"RX FIFO: {self.sm.rx_fifo()}")

                for name, ch in zip(self.ch_names, self.channels):
                    self.debug_dma(ch, name, 'in_loop')
                    self.debug_pio_status()
                    print("----------------------------------------------")
                    self.debug_register()

            if self.debug_buffer_enable:
                print("----------------------------------------------")
                print("DEBUG BUFFER:")
                self.debug_buffer(self.debug_bytes)

            print(".loop")

            pass

        print("<<<-------- FINISHED READING IMAGE ---------->>>")

        if debug:

            for name, ch in zip(self.ch_names, self.channels):
                self.debug_dma(ch, name, 'post_dma')
                self.debug_pio_status()

        self.sm.active(0)
        self.dma_img_read.active(0)
        self.dma_palette_ctrl.active(0)


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
        print(f"DEBUG REG >>> {deb1:08b}-{deb2:08b}-{deb3:08b}-{deb4:08b} <<<")

    def debug_dma(self, dma, base_addr, label):
        my_dict = dma.unpack_ctrl(dma.registers[3])
        active_txt = 'ACTIVE' if dma.active() else 'INACTIVE'
        print()
        print(f"DMA #{dma.channel} | ({active_txt}) ({label}):")
        print("-------------------------------------")
        # print(f". ........ {dma.registers[0]:08x} R \t........ {mem32[base_addr + 0x024]:08x} TX")
        print(f". ........ {dma.registers[0]:08x} R \t........ {dma.registers[9]:08x} TX")
        print(f". ........ {dma.registers[1]:08x} W \t........ {dma.registers[3]:08x} CTRL")

        print(f"*. CTRL UNPACKED |")
        print(f"                 v")
        for idx1, idx2 in zip(range(0, len(my_dict), 2), range(1, len(my_dict), 2)):
            # rangerange(0, len(my_dict), 2):
            keys = list(my_dict.keys())
            key1 = keys[idx1]
            key2 = keys[idx2]
            value1 = my_dict[key1]
            value2 = my_dict[key2]
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
        self.dma_img_read.close()
        self.dma_pixel_read.close()
        self.dma_palette.close()
        self.dma_pixel_out.close()
