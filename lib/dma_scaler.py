import sys

import time
import uctypes

import rp2
from machine import Pin, mem32
from rp2 import DMA, PIO, const

from framebuf import FrameBuffer

from dump_object import dump_object
from images.indexed_image import Image
import uctypes
from array import array
import utime

# 0x080 CH2_READ_ADDR
# 0x084 CH2_WRITE_ADDR
# 0x088 CH2_TRANS_COUNT
# 0x08c CH2_CTRL_TRIG
# 0x090 CH2_AL1_CTRL
# 0x094 CH2_AL1_READ_ADDR

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
        out_shiftdir=PIO.SHIFT_LEFT,
        in_shiftdir=PIO.SHIFT_RIGHT,
    )
    def pixel_demux():
        pull()              .side(0)[4]  # Pull 32 bits, set side pin to 0, wait 2 cycles
        # mov(y, null)        .side(1)[4]           # Set Y to 0 (source of zero bits)
        set(x, 3)           .side(0)[4]       # Set up loop counter (4 iterations, 0-3)

        label("loop")
        out(y, 4)           .side(1)[4]       # take in 4 bits
        in_(y, 8)
        push()

        jmp(x_dec, "loop")  .side(1)[4]        # Decrement counter and loop if not zero

        # irq(block, 0)

        # set(x, 3)               .side(1)[2]  # Set loop counter to 3 (4 iterations total, one per byte)
        #
        # label("loop")
        # out(y, 8)               .side(0)[2]  # Get 8 bits into y
        # mov(isr, y)             .side(1)[2]  # Copy y to ISR
        # in_(null, 24)           .side(0)[2]  # Shift right by 24, 4 MSB now in LSB
        #
        # mov(y, isr)             .side(0)[2]  # Restore y from ISR
        # in_(null, 28)           .side(1)[2]  # Shift right by 28, 4 LSB now in LSB
        # push(noblock)           .side(0)[2]  # Push second 4 bits (was LSB, still in LSB)
        #
        # jmp(x_dec, "loop")      .side(1)[2]  # Decrement x and jump if not zero

    dma_pixel_read = None
    dma_palette = None
    dma_pixel_out = None

    def init_pio(self):
        # Set up the PIO state machine
        # freq = 125 * 1000 * 1000
        freq = 10 * 1000 * 1000
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


    def __init__(self, display, channel2, channel3, channel4, channel5, channel6):

        self.display = display
        self.screen_width = self.display.width
        self.screen_height = self.display.height

        """ DMA Channels"""
        self.dma_img_read = channel2
        self.dma_pixel_read = channel3
        self.dma_palette = channel4
        self.dma_palette_ctrl = channel6
        self.dma_pixel_out = channel5

        debug_bytes = array("B", [0] * 64)
        self.debug_bytes = debug_bytes

        read_ctrl_block = array("I", [4])
        self.read_ctrl_block = read_ctrl_block

        self.init_pio()
        print(f"Screen dimensions: {self.screen_width}x{self.screen_height}")

    def dma_handler(self):
        print("Was handled")

    def pio_handler(self, event):
        """ Handle an IRQ from a SM"""
        print()
        print("+++ A PIO IRQ OCCURRED ++++")
        print()

    def setup_dma(self, read_addr, write_addr, sprite_width, sprite_height, palette_size, palette_read_addr):
        # Get the correct FIFO addresses

        tx_fifo_addr = 0x50300000 + 0x10
        rx_fifo_addr = 0x50300000 + 0x20

        print(f"Writing a {sprite_width}x{sprite_height} sprite")
        print(f"Address check: read:{read_addr:08x} write:{write_addr:08x}")
        print()

        #
        # for i in range(sprite_height):
        #     desc_write = int(write_addr + ((i * self.screen_width) * self.bytes_per_pixel))
        #     self.descriptors.append(desc_write)
        #     # self.descriptors[i * 4 + 3] = uctypes.addressof(self.descriptors) + ((i + 1) % sprite_height) * 16

        num_pixels = sprite_width * sprite_height

        print(f"DEBUG BYTES ADDR: 0x{uctypes.addressof(self.debug_bytes):08x}")

        """ Image Read DMA channel - CH #2 - (feeds SM) --------------------------------------- """
        pio_num = 0  # PIO program number
        sm_num = 0  # State Machine number
        DATA_REQUEST_INDEX = (pio_num << 3) + sm_num

        palette_read_addr_addr = uctypes.addressof(palette_read_addr)

        dma_img_read_ctrl = self.dma_img_read.pack_ctrl(
            size=2,
            inc_read=True,
            inc_write=False,
            treq_sel=DREQ_PIO1_TX0,
            chain_to=self.dma_pixel_read.channel,
        )
        self.dma_img_read.config(
            count=64,
            read=read_addr,
            write=PIO1_TX,
            # write=self.debug_bytes,
            ctrl=dma_img_read_ctrl,
        )
        # self.dma_img_read.irq(handler=dma_callback, hard=True)

        """ Pixel reader DMA channel - CH #3 - (post SM) ---------------------------- """

        dma_pixel_read_ctrl = self.dma_pixel_read.pack_ctrl(
            size=2,
            inc_read=False,
            inc_write=False,
            treq_sel=DREQ_PIO1_RX0,
            chain_to=self.dma_img_read.channel
        )
        self.dma_pixel_read.config(
            count=128,
            read=PIO1_RX,
            write=DMA_BASE_4 + DMA_TRANS_COUNT_TRIG,
            # write=self.debug_bytes,
            ctrl=dma_pixel_read_ctrl,
        )
        # self.dma_pixel_read.irq(handler=dma_callback, hard=True)

        # DMA_BASE = 0x50000000
        # DMA_WRITE = 0x0c4
        # 0x11c
        # value = DMA_BASE + CH4_AL1_TRANS_COUNT_TRIG
        # value = uctypes.addressof(self.dma_palette.registers) + (7 * 4)
        # mem32[DMA_BASE + DMA_WRITE] = value

        """ Palette DMA channel - CH #4 - --------------------------------------- """

        dma_palette_ctrl = self.dma_palette.pack_ctrl(
            size=2,  # 2 bytes per transfer \
            inc_read=True,
            inc_write=False,
            chain_to=self.dma_pixel_read.channel,
            ring_size=palette_size,
            ring_sel=False,
        )

        self.dma_palette.config(
            count=1,
            read=palette_read_addr,
            write=DMA_BASE_5 + CH5_READ_ADDR,
            # write=self.debug_bytes,
            ctrl=dma_palette_ctrl,
        )
        # self.dma_palette.irq(handler=dma_callback, hard=True)


        """ palette ch ctrl DMA channel - CH #6 - Reconfigures palette read addr ------------------- """
        dma_palette_ctrl_ctrl = self.dma_palette_ctrl.pack_ctrl(
            size=2,
            inc_read=False,
            inc_write=False,
            chain_to=self.dma_pixel_out.channel
        )
        self.dma_palette_ctrl.config(
            count=1,
            read=palette_read_addr_addr,
            write=DMA_BASE_4 + CH4_AL1_READ_ADDR,
            ctrl=dma_palette_ctrl_ctrl,
        )


        """ Pixel out DMA channel - CH #5 --------------------- """
        dma_pixel_out_ctrl = self.dma_pixel_out.pack_ctrl(
            size=1,  # 16bit pixels
            inc_read=False,
            inc_write=True,
            chain_to=self.dma_palette_ctrl.channel,
        )

        self.dma_pixel_out.config(
            count=2,
            read=0,
            write=write_addr,
            ctrl=dma_pixel_out_ctrl
        )

        print(f"DMA channels configured for sprite dimensions: {sprite_width}x{sprite_height}")

    def show(self, image: Image, x, y, width, height, palette_bytes):
        print("==== PIXELBYTES ====")
        # print(f"LEN: {len(image.pixel_bytes)}")

        read_addr = uctypes.addressof(image.pixel_bytes)
        print()
        # print(f"SRC IMG ADDR: 0x{read_addr:016x}")
        print()

        # write_addr = self.display.write_addr + ((y * self.screen_width) + x) * self.bytes_per_pixel
        write_addr = self.display.write_addr


        palette_size = len(palette_bytes)//2
        palette_bytes_addr = array("I", [0] * palette_size)
        palette_read_addr=uctypes.addressof(palette_bytes)

        for i in range(0, palette_size):
            palette_bytes_addr[i] = palette_read_addr + i * 4

        print("PALETTE BYTES ADDRS:")
        print(palette_bytes_addr)

        self.setup_dma(read_addr, write_addr, width, height, palette_size, palette_bytes_addr)

        self.debug_dma(self.dma_img_read, DMA_BASE_2, 'start')
        print(f"DMA 2 COUNT: {mem32[DMA_BASE_2 + 0x024]:08x}")
        self.debug_status(DMA_BASE_2 + 0x010, 2)

        self.debug_dma(self.dma_pixel_read, DMA_BASE_3, 'start')
        print(f"DMA 3 COUNT: {mem32[DMA_BASE_3 + 0x024]:08x}")
        self.debug_status(DMA_BASE_3 + 0x010, 3)

        self.debug_dma(self.dma_palette, DMA_BASE_4, 'start')
        print(f"DMA 4 COUNT: {mem32[DMA_BASE_4 + 0x024]:08x}")
        self.debug_status(DMA_BASE_4 + 0x010, 4)

        self.debug_dma(self.dma_palette_ctrl, DMA_BASE_6, 'start')
        print(f"DMA 6 COUNT: {mem32[DMA_BASE_6 + 0x024]:08x}")
        self.debug_status(DMA_BASE_6 + 0x010, 2)


        print(f"ADDR OF DEBUG_BYTES: {uctypes.addressof(self.debug_bytes):08x}")

        # Start the DMA transfer chain
        self.sm.active(1)
        time.sleep_ms(10)

        self.dma_img_read.active(1)
        self.dma_pixel_read.active(1)
        self.dma_palette.active(1)
        self.dma_palette_ctrl.active(1)
        self.dma_pixel_out.active(1)



        while self.dma_img_read.active():
            time.sleep_ms(1)
            print("=====================================================")
            self.debug_register()

            print(f"TX FIFO: {self.sm.tx_fifo()}")
            print(f"RX FIFO: {self.sm.rx_fifo()}")

            self.debug_dma(self.dma_img_read, DMA_BASE_2,'in_loop')
            self.debug_status(DMA_BASE_2 + 0x010, 2)

            # self.debug_dma(self.dma_img_read_reload, DMA_BASE_6, 'in_loop')
            # self.debug_status(DMA_BASE_6 + 0x010, 2)

            self.debug_dma(self.dma_pixel_read, DMA_BASE_3, 'in_loop')
            self.debug_status(DMA_BASE_3 + 0x010, 2)

            self.debug_dma(self.dma_palette, DMA_BASE_4, 'in_loop')
            self.debug_status(DMA_BASE_4 + 0x010, 2)

            print("----------------------------------------------")
            print()
            print("DEBUG BYTES")
            print()
            print("----------------------------------------------")

            self.debug_buffer(self.debug_bytes)
            print()
            print()

        self.debug_dma(self.dma_img_read, DMA_BASE_2, 'end')
        self.debug_status(DMA_BASE_2 + 0x010, 2)
        #
        # self.debug_dma(self.dma_img_read_reload, DMA_BASE_6, 'start')
        # self.debug_status(DMA_BASE_6 + 0x010, 2)

        self.debug_dma(self.dma_pixel_read, DMA_BASE_3, 'end')
        self.debug_status(DMA_BASE_3 + 0x010, 3)

        self.debug_dma(self.dma_palette, DMA_BASE_4, 'end')
        self.debug_status(DMA_BASE_4 + 0x010, 4)

        self.debug_register()

        # self.debug_buffer(self.debug_bytes)

        print(f"  RX FIFO level: {self.sm.rx_fifo()}")
        print(f"  TX FIFO level: {self.sm.tx_fifo()}")

        # print(f"IRQ: {irq_read:08x}")

        print(f"Transfer complete. Sprite dimensions: {width}x{height}")

    def status_to_bytes(self, status_int):
        status_int = status_int.to_bytes(4, 'big')
        status = [status_int[0], status_int[1], status_int[2], status_int[3]]
        return status

    def debug_status(self, addr, num):
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
        print()
        print(f"DMA #{dma.channel} | ACT: ({dma.active()}) ({label}):")
        print("-------------------------------")
        print(f"0. {dma.registers[0]:016x} R")
        print(f"1. {dma.registers[1]:016x} W")
        # print(f" 2. {dma.registers[9]:016x} TX")
        print(f"2. {mem32[base_addr + 0x024]:016x} TX")
        print(f"3. {dma.registers[3]:016x} CTRL")

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
