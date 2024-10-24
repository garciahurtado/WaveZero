from micropython import const
from machine import mem32

from uarray import array

from scaler.dma_scaler_const import *

DMA_DBG_TCR = const(0x804)

class ScalerDebugger():
    sm_indices = None
    sm_row_start = None
    channel_names = {}
    channels = {}
    debug_bytes = array("L", [0] * 16)

    def __init__(self, sm_indices, sm_row_start):
        self.sm_indices = sm_indices
        self.sm_row_start = sm_row_start

    def status_to_bytes(self, status_int):
        status_int = status_int.to_bytes(4, 'big')
        status = [status_int[0], status_int[1], status_int[2], status_int[3]]
        return status

    def debug_fifos(self):
        print()
        print("=====================================================")
        print(f"SM0 TX FIFO: {self.sm_indices.tx_fifo()}")
        print(f"SM0 RX FIFO: {self.sm_indices.rx_fifo()}")

        print("=====================================================")
        print(f"SM1 TX FIFO: {self.sm_row_start.tx_fifo()}")
        print(f"SM1 RX FIFO: {self.sm_row_start.rx_fifo()}")
        print("=====================================================")
        print()

    def debug_pio_status(self):
        print()
        print("SM0 -------------")
        inst_code = mem32[PIO1_BASE + SM0_INST_DEBUG]
        self.read_pio_opcode(inst_code)
        print("SM1 -------------")
        inst_code = mem32[PIO1_BASE + SM1_INST_DEBUG]
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

        tcr = mem32[DMA_ADDR + DMA_DBG_TCR]

        active_txt = 'ACTIVE' if dma.active() else 'INACTIVE'
        print()
        print(f"CH '{alias}' (#{dma.channel}) | ({active_txt}) | ({label}):")
        print("---------------------------------------------------")
        print(f". ........ {dma.registers[0]:08x} R \t........ {dma.registers[9]:08x} TX (current)")
        print(f". ........ {dma.registers[1]:08x} W \t........ {tcr:08x} TCR (next)")
        print(f". ........ {dma.registers[3]:08x} CTRL")
        print(f"*. CTRL UNPACKED |")
        print(f"                 v")
        for idx1, idx2 in zip(range(0, len(ctrl), 2), range(1, len(ctrl), 2)):
            keys = list(ctrl.keys())
            key1 = keys[idx1]
            key2 = keys[idx2]
            value1 = ctrl[key1]
            value2 = ctrl[key2]
            print(f".{key1:_<12} {value1:02x} \t\t .{key2:_<12} {value2:02x}")

    def debug_buffer(self, data_bytes):
        print(f"Debug Buffer Contents: ")
        print()

        """ all sizes in bytes"""
        rows = 4
        cols = 4
        out_str = ""

        for i in range(0, rows * cols):
            if (i and (i % cols) == 0):
                out_str += "\n"

            val = data_bytes[i]
            out_str += f"{val:08x}-"

        print(out_str)

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

    def get_debug_bytes(self):
        debug_bytes = self.debug_bytes

        for i in range(0, len(debug_bytes), 2):
            debug_bytes[i] = 0x12345678  # easier to see when its set vs 00000000
            debug_bytes[i + 1] = 0x90ABCDEF

        return debug_bytes

    def debug_dma_channel(self, idx, section=None):
        ch = self.channels[idx]
        ch_alias = self.channel_names[idx]
        ch_alias = ch_alias.upper()
        self.debug_dma(ch, ch_alias, section, idx)
        self.debug_pio_status()
        print("- - - - - - - - - - - - - - - - - - - - - ")
        self.debug_register()
        self.debug_fifos()

