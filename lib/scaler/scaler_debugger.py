from rp2 import PIO
from machine import mem32
from uarray import array
from uctypes import addressof

from scaler.const import *
from utils import aligned_buffer

class ScalerDebugger():
    sm_indices = None
    sm_row_start = None
    sm_indexed_scaler = None

    channel_names = {}
    channels = {}

    def __init__(self, sm_indices=None, sm_row_start=None, sm_row_scale=None, sm_indexed_scaler=None, dma_ch=None):
        self.sm_indices = sm_indices
        self.sm_row_start = sm_row_start
        self.sm_row_scale = sm_row_scale
        self.sm_indexed_scaler = sm_indexed_scaler
        self.dma_ch = dma_ch

    def status_to_bytes(self, status_int):
        status_int = status_int.to_bytes(4, 'big')
        status = [status_int[0], status_int[1], status_int[2], status_int[3]]
        return status

    def debug_fifos(self):
        # print()
        # print("=====================================================")
        # print(f"SM0 TX FIFO: {self.sm_indices.tx_fifo()}")
        # print(f"SM0 RX FIFO: {self.sm_indices.rx_fifo()}")
        #
        # print("=====================================================")
        # print(f"SM1 TX FIFO: {self.sm_row_start.tx_fifo()}")
        # print(f"SM1 RX FIFO: {self.sm_row_start.rx_fifo()}")
        #
        # print("=====================================================")
        # print(f"SM2 TX FIFO: {self.sm_row_scale.tx_fifo()}")
        # print(f"SM2 RX FIFO: {self.sm_row_scale.rx_fifo()}")
        # print("=====================================================")
        # print()

        print("=====================================================")
        print(f"SM3 TX FIFO: {self.sm_indexed_scaler.tx_fifo()}")
        print(f"SM3 RX FIFO: {self.sm_indexed_scaler.rx_fifo()}")
        print("=====================================================")
        print()

    def debug_pio_status(self, pio=0, sm=0):
        print(f"-- STATE MACHINE STATUS (PIO {pio}, SM {sm})")

        if pio == 0:
            pio_base = PIO0_BASE
        elif pio == 1:
            pio_base = PIO1_BASE

        if sm == 0:
            reg_line = SM0_ADDR
            reg_inst = SM0_INST_DEBUG
        elif sm == 1:
            reg_line = SM1_ADDR
            reg_inst = SM1_INST_DEBUG

        line_num = mem32[pio_base + reg_line] & 0x1F  # Mask bits 4:0
        line_num_rev = 31 - line_num
        inst_code = mem32[pio_base + reg_inst] & 0xFFFF  # Keep 16 LSBs
        print("----------------------")
        print(f"-- INST: (line {line_num_rev} / {line_num}) -- (from zero / from 32)")
        self.read_pio_opcode(inst_code)
        print("----------------------")
        self.debug_pio_regs(pio, sm)
        print()

    def debug_pio_regs(self, pio=0, sm=0):
        if pio == 0:
            pio_base = PIO0_BASE
        elif pio == 1:
            pio_base = PIO1_BASE

        debug_addr = pio_base + 0x008

        txstall = (mem32[debug_addr] >> 24) & 0xF
        txover = (mem32[debug_addr] >> 16) & 0xF
        rxunder = (mem32[debug_addr] >> 8) & 0xF
        rxstall = (mem32[debug_addr]) & 0xF
        print("              TXSTALL    TXOVER     RXUNDER    RXSTALL")
        print(f"DEBUG REG >>> {txstall:08b} - {txover:08b} - {rxunder:08b} - {rxstall:08b} <<<")

    def debug_dma(self, dma, alias, label, index):
        ctrl = dma.unpack_ctrl(dma.registers[3])
        DMA_NAME = f"DMA_BASE_{index}"

        active_txt = 'ACTIVE' if dma.active() else 'INACTIVE'
        print()
        print(f"CH '{alias}' (DMA{dma.channel}) | ({active_txt}) | ({label}):")
        print("---------------------------------------------------")
        print(f". ........ {dma.registers[0]:08X} R \t........ {dma.registers[9]:08X} TX (current)")
        print(f". ........ {dma.registers[1]:08X} W \t........ {0:08X} TCR (next)")
        print(f". ........ {dma.registers[3]:08X} CTRL")
        print(f"*. CTRL UNPACKED |")
        print(f"                 v")

        keys = list(ctrl.keys())
        for idx1, idx2 in zip(range(0, len(ctrl), 2), range(1, len(ctrl), 2)):
            key1 = keys[idx1]
            key2 = keys[idx2]
            value1 = ctrl[key1]
            value2 = ctrl[key2]
            print(f".{key1:_<12} {value1:02X} \t\t .{key2:_<12} {value2:02X}")

    def get_debug_bytes(self, count=32, byte_size=2, aligned=False):
        """
        count: number of elements
        byte_size: 0 or 1 for bytes, 2 for words
        """
        if byte_size >= 2:
            if aligned:
                buf = aligned_buffer(count)
                debug_bytes = array("L", [0] * buf)
            else:
                debug_bytes = array("L", [0] * count)  # 32-bit words

            init_value = 0x12345678 # much more obvious than zeros
        else:
            debug_bytes = array("B", [0] * count)  # bytes
            init_value = 0x78  # Just lowest byte

        # Initialize all elements
        for i in range(len(debug_bytes)):
            debug_bytes[i] = init_value

        return debug_bytes

    def print_debug_bytes(self, data_bytes, format='hex', num_cols=4):
        print(
            f"Debug Buffer Contents ({len(data_bytes)} {'bytes' if isinstance(data_bytes[0], int) and data_bytes[0] < 256 else 'words'})")
        print()

        # Calculate actual number of rows needed
        total_items = len(data_bytes)
        rows = (total_items + num_cols - 1) // num_cols

        for row in range(rows):
            for col in range(num_cols):
                idx = row * num_cols + col
                if idx >= total_items:
                    break

                val = data_bytes[idx]
                if format == 'bin':
                    out_str = f"{val:08b}-"
                else:
                    out_str = f"{val:08X}-"
                print(out_str, end='')
            print()

    def read_pio_opcode(self, instr):
        opcode = (instr & 0xE000) >> 13

        opcodes = [
            "JMP", "WAIT", "IN", "OUT", "PUSH/PULL", "MOV", "IRQ", "SET"
        ]

        if opcode < len(opcodes):

            if opcode == 0:  # JMP
                print("JMP")
                condition = (instr >> 5) & 0x7
                address = instr & 0x1F
                conditions = ["ALWAYS", "!X", "X--", "!Y", "Y--", "X!=Y", "PIN", "!OSRE"]
                print(f"Condition: {conditions[condition]}, Address: {address}")
            elif opcode == 4:  # PUSH/PULL
                if instr & 0x80:
                    print("PULL")
                else:
                    print("PUSH")
                if instr & 0x60:  # Check if blocking
                    print("(blocking)")
                else:
                    print("(non-blocking)")
            else:
                print(f"{opcodes[opcode]}")

        else:
            print("Unknown instruction")

    def debug_all_dma_channels(self, idx, section=None):
        ch = self.channels[idx]
        ch_alias = self.channel_names[idx]
        ch_alias = ch_alias.upper()
        self.debug_dma(ch, ch_alias, section, idx)
        self.debug_pio_status()
        print("- - - - - - - - - - - - - - - - - - - - - ")
        self.debug_pio_regs()
        self.debug_fifos()

    def debug_addresses(self, display, image, x=0, y=0):
        # write_addr_base = display.write_addr
        write_offset = (((y * display.width) + x) * 2) - 8  # since the display is 16 bit, we multiply x 2
        # write_addr = write_addr_base + write_offset

        print("============================================")

        # print(f"DISPLAY START ADDR: 0x{write_addr_base:08X}")
        print(f"READING {len(image.pixel_bytes)} BYTES FROM SPRITE ADDR: 0x{addressof(image.pixel_bytes):08X}")
        print(f"X: {x} Y: {y}")

        print("DISPLAY & MEM ADDR:")
        print("------------------------")
        print(f"\twidth: {display.width}px")
        print(f"\theight: {display.height}px")
        print(f"\tdisplay_out_start (offset): 0x{display.buf0_addr:08X} + 0x{display.buf0_addr:08X}")
        # print(f"\tsprite_out_addr + offset: 0x{write_addr:08X}")
        print(f"\timg_read_addr: 0x{image.pixel_bytes_addr:08X}")
        print(f"\tcolor_addr: 0x{addressof(image.palette_bytes):08X}")

    def debug_sm_pins(self, sm):
        """Debug PIO state machine pin configuration"""
        # Get base address of PIO
        pio_base = PIO0_BASE if sm._pio == PIO(0) else PIO1_BASE

        # Calculate state machine offset
        sm_offset = 0xc8 + (sm._sm * 0x18)  # 0xc8 is offset of first SM's registers

        # Get control registers
        pinctrl = mem32[pio_base + sm_offset + 0x14]  # PINCTRL offset
        execctrl = mem32[pio_base + sm_offset + 0x04]  # EXECCTRL offset

        print("\n=== State Machine Pin Configuration ===")

        # OUT pins
        out_base = (pinctrl >> 5) & 0x1F
        out_count = (pinctrl >> 0) & 0x1F
        print(f"OUT pins: base={out_base}, count={out_count}")
        print(f"  Using GPIOs: {list(range(out_base, out_base + out_count))}")

        # IN pins
        in_base = (pinctrl >> 15) & 0x1F
        print(f"IN base pin: {in_base}")

        # SET pins
        set_base = (pinctrl >> 10) & 0x1F
        set_count = (pinctrl >> 26) & 0x3F
        print(f"SET pins: base={set_base}, count={set_count}")
        print(f"  Using GPIOs: {list(range(set_base, set_base + set_count))}")

        # Side-set pins
        sideset_base = (pinctrl >> 20) & 0x1F
        sideset_count = (pinctrl >> 29) & 0x07
        print(f"Side-set: base={sideset_base}, count={sideset_count}")
        if sideset_count:
            print(f"  Using GPIOs: {list(range(sideset_base, sideset_base + sideset_count))}")

        # JMP pin
        jmp_pin = (execctrl >> 24) & 0x1F
        print(f"JMP pin: {jmp_pin}")

        print("\nCurrent GPIO states:")
        gpio_oe = mem32[pio_base + 0x40]  # DBG_PADOE
        gpio_out = mem32[pio_base + 0x3C]  # DBG_PADOUT
        print(f"GPIO Output Enable: 0x{gpio_oe:08x}")
        print(f"GPIO Output Values: 0x{gpio_out:08x}")

    def debug_interp(self):
        print("INTERP0 (Write addresses):")
        print(f"  BASE0: 0x{mem32[INTERP0_BASE0]:08x}")
        print(f"  BASE1: 0x{mem32[INTERP0_BASE1]:08x}")
        print(f"  BASE2: 0x{mem32[INTERP0_BASE2]:08x}")
        print(f"  ACCU0: 0x{mem32[INTERP0_ACCUM0]:08x}")
        print(f"  ACCU1: 0x{mem32[INTERP0_ACCUM1]:08x}")

        print("INTERP1 (Read addresses):")
        print(f"  BASE0: 0x{mem32[INTERP1_BASE0]:08x}")
        print(f"  BASE1: 0x{mem32[INTERP1_BASE1]:08x}")
        print(f"  BASE2: 0x{mem32[INTERP1_BASE2]:08x}")
        print(f"  ACCU0: 0x{mem32[INTERP1_ACCUM0]:08x}")
        print(f"  ACCU1: 0x{mem32[INTERP1_ACCUM1]:08x}")