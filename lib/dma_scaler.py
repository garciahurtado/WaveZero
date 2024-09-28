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

    dma_img_read = None

    @rp2.asm_pio(
        sideset_init=PIO.OUT_LOW,
        out_shiftdir=PIO.SHIFT_RIGHT,
        in_shiftdir=PIO.SHIFT_RIGHT,
    )
    def pixel_demux():
        pull()              .side(0)[0]       # Pull 32 bits (4 bytes), set side pin to 0, wait 2 cycles
        set(x, 7)           .side(1)[0]       # Set up loop counter (8 iterations, 0-7)

        label("loop")
        out(y, 4)           .side(0)[0]       # pull 4 bits from OSR
        in_(y, 8)                             # spit them out as 8
        push()

        jmp(x_dec, "loop")  .side(1)[0]        # Decrement counter and loop if not zero


    dma_pixel_read = None
    dma_palette = None
    dma_pixel_out = None

    def init_pio(self):
        # Set up the PIO state machine
        # freq = 125 * 1000 * 1000
        freq = 1 * 1000 * 1000
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


    def __init__(self, display, palette_size, channel2, channel3, channel4, channel5, channel6, channel7):

        self.display = display
        self.screen_width = self.display.width
        self.screen_height = self.display.height
        self.palette_size = palette_size

        """ DMA Channels"""
        self.dma_img_read = channel2
        self.dma_pixel_read = channel3
        self.dma_pixel_read_rst = channel7
        self.dma_palette = channel4
        self.dma_palette_ctrl = channel6
        self.dma_pixel_out = channel5

        debug_bytes = array("B", [0] * 256)
        self.debug_bytes = debug_bytes

        read_ctrl_block = array("I", [4])
        self.read_ctrl_block = read_ctrl_block

        self.palette_buffer = array("H", [0x00FF, 0xFF00, 0xF00F])
        self.palette_buffer_addr = addressof(self.palette_buffer)

        self.single_colors_addrs = array("I", [0] * palette_size)

        palette_size = len(self.single_colors_addrs)
        for i in range(palette_size):
            self.single_colors_addrs[i] = self.palette_buffer_addr + (i*2)

        print(f"PALETTE COLOR ADDRS ({palette_size})")
        print()

        for i in range(palette_size):
            print(f"0x{self.single_colors_addrs[i]:08x}")

        print()


        self.count_rst = array("I", [4])
        self.count_rst_addr = addressof(self.count_rst)
        print(f"COUNT RESETTER: {self.count_rst} addr {self.count_rst_addr}")

        self.init_pio()
        print(f"Screen dimensions: {self.screen_width}x{self.screen_height}")

    def dma_handler(self):
        print("Was handled")

    def pio_handler(self, event):
        """ Handle an IRQ from a SM"""
        print()
        print("+++ A PIO IRQ OCCURRED ++++")
        print()

    def setup_dma(self, read_addr, write_addr, sprite_width, sprite_height, palette_size):
        # Get the correct FIFO addresses

        # for i in range(sprite_height):
        #     desc_write = int(write_addr + ((i * self.screen_width) * self.bytes_per_pixel))
        #     self.descriptors.append(desc_write)
        #     # self.descriptors[i * 4 + 3] = addressof(self.descriptors) + ((i + 1) % sprite_height) * 16

        num_pixels = sprite_width * sprite_height

        """ Image Read DMA channel - CH #2 - (feeds SM) --------------------------------------- """
        dma_img_read_ctrl = self.dma_img_read.pack_ctrl(
            size=2,
            inc_read=True,
            inc_write=False,
            treq_sel=DREQ_PIO1_TX0,
            chain_to=self.dma_pixel_read.channel,
        )
        self.dma_img_read.config(
            count=num_pixels//2,
            read=read_addr,
            write=PIO1_TX,
            ctrl=dma_img_read_ctrl,
            trigger=True
        )
        # self.dma_img_read.irq(handler=dma_callback, hard=True)

        """ Pixel reader DMA channel - CH #3 - (post SM) ---------------------------- """

        dma_pixel_read_ctrl = self.dma_pixel_read.pack_ctrl(
            size=2,
            inc_read=False,
            inc_write=False,
            treq_sel=DREQ_PIO1_RX0,
            # chain_to=self.dma_img_read.channel,
            # chain_to=self.dma_palette.channel,
            high_pri=True,
            bswap=True,
        )
        self.dma_pixel_read.config(
            count=num_pixels,
            read=PIO1_RX,
            write=DMA_BASE_4 + DMA_TRANS_COUNT_TRIG,
            # write=self.debug_bytes,
            ctrl=dma_pixel_read_ctrl,
            trigger=True
        )
#         self.dma_pixel_read.irq(handler=dma_callback, hard=True)

        # DMA_BASE = 0x50000000
        # DMA_WRITE = 0x0c4
        # 0x11c
        # value = DMA_BASE + CH4_AL1_TRANS_COUNT_TRIG
        # value = addressof(self.dma_palette.registers) + (7 * 4)
        # mem32[DMA_BASE + DMA_WRITE] = value

        """ Palette DMA channel - CH #4 - --------------------------------------- """

        dma_palette_ctrl = self.dma_palette.pack_ctrl(
            size=2,  # 2 bytes per transfer \
            inc_read=True,
            inc_write=False,
            chain_to=self.dma_pixel_out.channel,
            # chain_to=self.dma_img_read.channel,
            ring_size=3,
            ring_sel=False,
            bswap=True,
        )

        self.dma_palette.config(
            count=0,
            read=self.single_colors_addrs,
            write=DMA_BASE_5 + CH5_AL1_READ_ADDR,
            ctrl=dma_palette_ctrl,
        )
#         self.dma_palette.irq(handler=dma_callback, hard=True)

        """ Pixel out DMA channel - CH #5 --------------------- """
        dma_pixel_out_ctrl = self.dma_pixel_out.pack_ctrl(
            size=1,  # 16bit pixels
            inc_read=False,
            inc_write=True,
            chain_to=self.dma_pixel_read.channel,
        )

        self.dma_pixel_out.config(
            count=1,
            read=0,
            write=write_addr,
            ctrl=dma_pixel_out_ctrl
        )
        self.dma_pixel_out.irq(handler=dma_callback, hard=True)

        """ palette ch ctrl DMA channel - CH #6 - Reconfigures palette read addr ------------------- """
        dma_palette_ctrl_ctrl = self.dma_palette_ctrl.pack_ctrl(
            size=2,
            inc_read=False,
            inc_write=False,
            chain_to=self.dma_pixel_out.channel
        )
        self.dma_palette_ctrl.config(
            count=1,
            read=self.palette_buffer_addr,
            write=DMA_BASE_4 + CH4_READ_ADDR,
            ctrl=dma_palette_ctrl_ctrl,
        )
#         self.dma_palette_ctrl.irq(handler=dma_callback, hard=True)

        """ Reload #3 COUNT - CH #7 --------------------- """
        dma_pixel_read_rst_ctrl = self.dma_pixel_read_rst.pack_ctrl(
            size=2,
            inc_read=False,
            inc_write=False,
            chain_to=self.dma_img_read.channel
        )

        self.dma_pixel_read_rst.config(
            count=1,
            read=self.count_rst_addr,
            write=CH3_AL1_TRANS_COUNT_TRIG,
            ctrl=dma_pixel_read_rst_ctrl
        )
#         self.dma_pixel_read_rst.irq(handler=dma_callback, hard=True)


    def show(self, image: Image, x, y, width, height, palette_size):
        print("==== PIXELBYTES SIZE ====")
        print(f"LEN: {len(image.pixel_bytes)}")

        read_addr = addressof(image.pixel_bytes)

        # print(f"SRC IMG ADDR: 0x{read_addr:016x}")

        # write_addr = self.display.write_addr + ((y * self.screen_width) + x) * self.bytes_per_pixel
        write_addr = self.display.write_addr
        write_offset = ((y * self.screen_width) + x) * 2 # since the display is 16 bit, we multiply x 2
        num_pixels = width * height

        print(f"DRAWING AT {x},{y} ({width}x{height}) COLORS: {palette_size}")
        print(f"OFFSET: {write_offset}")
        print(f"READING {num_pixels} PIXELS in {len(image.pixel_bytes)} BYTES")

        write_addr += write_offset

        # palette_size = len(palette_bytes)//2
        # palette_bytes_addrs = array("I", [0] * palette_size)
        # palette_read_addr=addressof(palette_bytes)

        # for i in range(0, palette_size):
        #     addr = palette_read_addr + (i * 4)
        #     # print(f"ADDED {addr} to palette")
        #     palette_bytes_addrs[i] = addr

        prof.start_profile('scaler.setup_dma')
        self.setup_dma(read_addr, write_addr, width, height, palette_size)
        prof.end_profile('scaler.setup_dma')

        #
        # print("PALETTE BYTES ADDRS:")
        # print(palette_bytes_addrs)
        #
        #
        # self.debug_dma(self.dma_img_read, DMA_BASE_2, 'start')
        # print(f"DMA 2 COUNT: {mem32[DMA_BASE_2 + 0x024]:08x}")
        # self.debug_pio_status()
        #
        # self.debug_dma(self.dma_pixel_read, DMA_BASE_3, 'start')
        # print(f"DMA 3 COUNT: {mem32[DMA_BASE_3 + 0x024]:08x}")
        # self.debug_pio_status()
        #
        # self.debug_dma(self.dma_palette, DMA_BASE_4, 'start')
        # print(f"DMA 4 COUNT: {mem32[DMA_BASE_4 + 0x024]:08x}")
        # self.debug_pio_status()
        #
        # self.debug_dma(self.dma_pixel_out, DMA_BASE_5, 'start')
        # print(f"DMA 5 COUNT: {mem32[DMA_BASE_5 + 0x024]:08x}")
        # self.debug_pio_status()
        #
        # self.debug_dma(self.dma_palette_ctrl, DMA_BASE_6, 'start')
        # print(f"DMA 6 COUNT: {mem32[DMA_BASE_6 + 0x024]:08x}")
        # self.debug_pio_status()
        #
        # self.debug_dma(self.dma_pixel_read_rst, DMA_BASE_7, 'start')
        # print(f"DMA 7 COUNT: {mem32[DMA_BASE_7 + 0x024]:08x}")
        # self.debug_pio_status()

        # print(f"ADDR OF DEBUG_BYTES: {addressof(self.debug_bytes):08x}")

        # Start the DMA transfer chain
        self.sm.active(1)
        self.dma_img_read.active(1)
        self.dma_pixel_read.active(1)
        self.dma_palette.active(1)
        self.dma_palette_ctrl.active(1)
        self.dma_pixel_out.active(1)
        self.dma_pixel_read_rst.active(1)

        # self.debug_register()

        time.sleep_ms(2)

        """ As far as DMA goes, active and busy are the same thing """
        while (self.dma_img_read.active() or
               self.dma_pixel_out.active()):

            print("=====================================================")
            self.debug_register()

            print(f"TX FIFO: {self.sm.tx_fifo()}")
            print(f"RX FIFO: {self.sm.rx_fifo()}")

            self.debug_dma(self.dma_img_read, DMA_BASE_2,'in_loop')
            self.debug_pio_status()

            self.debug_dma(self.dma_pixel_read, DMA_BASE_3, 'in_loop')
            self.debug_pio_status()

            self.debug_dma(self.dma_palette, DMA_BASE_4, 'in_loop')
            self.debug_pio_status()

            self.debug_dma(self.dma_pixel_out, DMA_BASE_5, 'in_loop')
            self.debug_pio_status()

            self.debug_dma(self.dma_palette_ctrl, DMA_BASE_6, 'in_loop')
            self.debug_pio_status()
            #
            # print("----------------------------------------------")
            self.debug_register()
            print("----------------------------------------------")
            #
            # self.debug_buffer(self.debug_bytes)
            print()

            pass


        # self.debug_dma(self.dma_img_read, DMA_BASE_2, 'end')
        # self.debug_pio_status()
        # #
        # # self.debug_dma(self.dma_img_read_reload, DMA_BASE_6, 'start')
        # # self.debug_status(DMA_BASE_6 + 0x010, 2)
        #
        # self.debug_dma(self.dma_pixel_read, DMA_BASE_3, 'end')
        # self.debug_pio_status()
        #
        # self.debug_dma(self.dma_palette, DMA_BASE_4, 'end')
        # self.debug_pio_status()
        #
        # self.debug_dma(self.dma_pixel_out, DMA_BASE_5, 'end')
        # self.debug_pio_status()
        #
        # self.debug_dma(self.dma_palette_ctrl, DMA_BASE_6, 'end')
        # self.debug_pio_status()
        #
        # self.debug_dma(self.dma_pixel_read_rst, DMA_BASE_7, 'end')
        # self.debug_pio_status()
        #
        # self.debug_register()
        # self.debug_buffer(self.debug_bytes)
        #
        # print(f"  RX FIFO level: {self.sm.rx_fifo()}")
        # print(f"  TX FIFO level: {self.sm.tx_fifo()}")

        # print(f"IRQ: {irq_read:08x}")

        # print(f"Transfer complete. Sprite dimensions: {width}x{height}")

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
        print(f". {dma.registers[0]:016x} R \t{mem32[base_addr + 0x024]:016x} TX")
        print(f". {dma.registers[1]:016x} W \t{dma.registers[3]:016x} CTRL")

        print(f"4. CTRL UNPACKED |")
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
