from rp2 import PIO
from machine import mem32
import sys

from uarray import array
from uctypes import addressof
import sys

from scaler.const import *
from utils import aligned_buffer

def printb(message):
    """ Print a string and then print a series of backspaces equal to its length, to implement statically positioned
     text in the terminal """
    num_back = len(message)
    eraser = '\b' * num_back
    print(message, end='')
    print(eraser, end='')

def printc(message, color=INK_RED, newline=True):
    if newline:
        print(color, message, INK_END)
    else:
        print(color, message, INK_END, end="")


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
        inst_code = mem32[pio_base + reg_inst] & 0xFFFF  # Keep 16 LSBs

        # This one is tricky: we have to count the instructions from the bottom of the program, starting at zero,
        #  but if we haven't added wrap() at the bottom, it will be added silently, so if the line number is off
        # by one, that is why
        print("----------------------")
        print(f"-- INST#: {line_num} (backwards)")
        self.read_pio_opcode(inst_code)
        print("----------------------")

        self.debug_pio_regs(0)
        self.debug_pio_regs(1)
        print()

    def debug_pio_regs(self, pio=0):
        if pio == 0:
            pio_base = PIO0_BASE
        elif pio == 1:
            pio_base = PIO1_BASE

        debug_addr = pio_base + 0x008
        txstall = (mem32[debug_addr] >> 24) & 0xF
        txover = (mem32[debug_addr] >> 16) & 0xF
        rxunder = (mem32[debug_addr] >> 8) & 0xF
        rxstall = (mem32[debug_addr]) & 0xF
        print(f"PIO{pio} (0x{debug_addr:08X})     TXSTALL    TXOVER     RXUNDER    RXSTALL")
        print(f"  FIFO STATUS     >>> {txstall:08b} - {txover:08b} - {rxunder:08b} - {rxstall:08b} <<<")

    def debug_dma(self, dma, alias, full=True):
        # full = False
        ctrl = dma.unpack_ctrl(dma.registers[3])
        count = dma.count
        index = dma.channel

        DMA_NAME = f"DMA_BASE_{index}"

        active_txt = '(** ON **)' if dma.active() else '    off   '
        print("---------------------------------------------------")
        ch_name = f"CH {alias} "
        print(f"{ch_name:<17} - DMA-{dma.channel} | {active_txt} | count: {count:05.}")
        print("---------------------------------------------------")
        if not full:
            return

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

    def get_debug_bytes(self, count=256, byte_size=2, aligned=False):
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

    def print_debug_bytes(self, data_bytes, format='hex', num_cols=16):
        print(
            f"Debug Buffer Contents ({len(data_bytes)} {'bytes' if isinstance(data_bytes[0], int) and data_bytes[0] < 256 else 'words'})")
        print()

        # Calculate actual number of rows needed
        total_items = len(data_bytes)
        rows = (total_items + num_cols - 1) // num_cols

        for row in range(rows):
            print(f"{row:02.}. ", end="")
            for col in range(num_cols):
                idx = row * num_cols + col
                if idx >= total_items:
                    break

                val = data_bytes[idx]
                if format == 'bin':
                    out_str = f"{val:08b}-"
                else:
                    hex_str = str(hex(val))[-2:]
                    out_str = f"..{hex_str}"
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
        self.debug_dma(ch, ch_alias)
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

    def debug_irq_priorities(self, ipr_values):
        print("IRQ PRIORITIES:")
        print("--------------------")
        print("         | INT 4n+3      | INT 4n+2      | INT 4n+1      | INT 4n+0      |")
        print("Register | [31:28]       | [23:20]       | [15:12]       | [7:4]         |")
        print("---------+---------------+---------------+---------------+---------------+")

        for n, reg_value in enumerate(ipr_values):
            # Extract only the significant 4 bits from each 8-bit field
            pri_n3 = (reg_value >> 28) & 0xF  # Top 4 bits of byte at [31:24]
            pri_n2 = (reg_value >> 20) & 0xF  # Top 4 bits of byte at [23:16]
            pri_n1 = (reg_value >> 12) & 0xF  # Top 4 bits of byte at [15:8]
            pri_n0 = (reg_value >> 4) & 0xF  # Top 4 bits of byte at [7:0]

            # Calculate actual interrupt numbers
            int_n3 = 4 * n + 3
            int_n2 = 4 * n + 2
            int_n1 = 4 * n + 1
            int_n0 = 4 * n

            # Format row with both binary and hex representations
            print(
                f"IPR{n:<6} | {pri_n3:04b} (0x{pri_n3:X}) {int_n3:<2} | {pri_n2:04b} (0x{pri_n2:X}) {int_n2:<2} | {pri_n1:04b} (0x{pri_n1:X}) {int_n1:<2} | {pri_n0:04b} (0x{pri_n0:X}) {int_n0:<2} |")

    def debug_irq_dma_enabled(self, iser_addr):
        """ ISER: Interrupt Set-Enable Register
        32 bit register where each bit is an enable for an IRQ number
        This is left as a parameter so that you can check INTE, INTF and INTS
        """
        n = 0

        print("DMA IRQ ENABLE STATUS:")
        print("-----------------------")
        print("               | Enabled Interrupts")
        print("Register       | (1 = enabled, 0 = disabled)")
        print("---------------+----------------------------------------------")

        dma_irqs = [10, 11, 12, 13]
        iser_val = mem32[iser_addr]
        print(f"ISER_REG: {n:<5}| {iser_val:032b}")
        print("---------------+----------------------------------------------")

        # Check each bit in the register
        for i, irq_id in enumerate(dma_irqs):
            if (iser_val & (1 << irq_id)) != 0:
                print(f"IRQ_DMA_{i:<7}| ENABLED")
            else:
                print(f"IRQ_DMA_{i:<7}| disabled")

        print("---------------+----------------------------------------------")

    def debug_irq_pio_enabled(self, iser_addr):
        """ ISER: Interrupt Set-Enable Register
        32 bit register where each bit is an enable for an IRQ number
        This is left as a parameter so that you can check INTE, INTF and INTS
        """
        n = 0

        print("PIO IRQ ENABLE STATUS:")
        print("-----------------------")
        print("               | Enabled Interrupts")
        print("Register       | (1 = enabled, 0 = disabled)")
        print("---------------+----------------------------------------------")

        pio_irqs = [8, 9, 10, 11, 12, 13, 14, 15] # All 8 SMs for this PIO
        iser_val = mem32[iser_addr]

        print(f"ISER_REG: {n:<5}| {iser_val:032b}")
        print("---------------+----------------------------------------------")

        # Check each bit in the register
        for i, irq_id in enumerate(pio_irqs):
            if (iser_val & (1 << irq_id)) != 0:
                print(f"SM_{i:<7}| ENABLED")
            else:
                print(f"SM_{i:<7}| disabled")

        print("---------------+----------------------------------------------")

    def debug_irq_pending(self, ispr_values):
        print("IRQ PENDING STATUS:")
        print("------------------------")
        print("         | Pending Interrupts")
        print("Register | (1 = pending, 0 = not pending)")
        print("---------+----------------------------------------------------")

        for n, reg_value in enumerate(ispr_values):
            pending_irqs = []

            # Check each bit in the register
            for bit in range(32):
                if (reg_value & (1 << bit)) != 0:
                    # This interrupt is pending - calculate its IRQ number
                    irq_num = n * 32 + bit
                    pending_irqs.append(f"{irq_num}")

            # Format the output showing the pending IRQs
            if pending_irqs:
                pending_list = ", ".join(pending_irqs)
                print(f"ISPR{n:<5}| {reg_value:032b}")
                print(f"         | Pending IRQs: {pending_list}")
            else:
                print(f"ISPR{n:<5}| {reg_value:032b}")
                print(f"         | No pending IRQs")

            print("---------+----------------------------------------------------")

    def debug_sprite(self, mem_addr, width=16, height=16):
        """
        Render a 4-bit indexed image from a memory address in a table layout.

        Args:
            memory_address (int): The starting memory address of the image data.
            width (int): The width of the table (number of pixels per row).
            height (int): The height of the table (number of rows).
        """
        import uctypes

        # Access the memory as a byte array
        image_data = uctypes.bytearray_at(mem_addr, (width * height + 1) // 2)

        # Iterate over rows
        for y in range(height):
            row = []
            for x in range(width):
                # Calculate the byte and nibble index
                byte_index = (y * width + x) // 2
                is_high_nibble = (x % 2 == 0)

                # Extract the nibble (4 bits)
                if is_high_nibble:
                    pixel = (image_data[byte_index] >> 4) & 0xF
                else:
                    pixel = image_data[byte_index] & 0xF

                # Map the pixel value to a single-digit color (1-9)
                color = pixel if 1 <= pixel <= 9 else "." # 0 maps to '.'
                row.append(str(color))

            # Print the row as a table
            print(" ".join(row))

    def debug_sprite_rgb565(self, mem_addr, width=16, height=16):
        """
        Render an RGB565 image from a memory address in a table layout.
        Each pixel is mapped to an index (0-9) based on a predefined palette.

        Args:
            mem_addr (int): The starting memory address of the image data.
            width (int): The width of the table (number of pixels per row).
            height (int): The height of the table (number of rows).
        """
        import uctypes

        # Define a simple palette mapping brightness to indices (0-9)
        # 0 = black, 9 = white, intermediate values are mapped linearly
        def map_to_index(rgb565):
            # Extract RGB components from RGB565
            red = (rgb565 >> 11) & 0x1F  # 5 bits for red
            green = (rgb565 >> 5) & 0x3F  # 6 bits for green
            blue = rgb565 & 0x1F  # 5 bits for blue

            # Normalize RGB values to 0-255 range
            red = (red * 255) // 31
            green = (green * 255) // 63
            blue = (blue * 255) // 31

            # Calculate brightness (0-255)
            brightness = (red + green + blue) // 3

            # Map brightness to an index (0-9)
            return min(brightness // 28, 9)  # 255 / 9 ≈ 28

        # Access the memory as a byte array
        image_data = uctypes.bytearray_at(mem_addr, width * height * 2)  # 2 bytes per pixel (RGB565)

        print(f"** IMAGE AT 0x{mem_addr:08X} **")
        # Iterate over rows
        for y in range(height):
            row = []
            for x in range(width):
                # Calculate the byte index for the current pixel
                byte_index = (y * width + x) * 2

                # Read the two bytes for the RGB565 pixel
                pixel_low = image_data[byte_index]  # Lower byte
                pixel_high = image_data[byte_index + 1]  # Higher byte

                # Combine the two bytes into a 16-bit RGB565 value
                rgb565 = (pixel_high << 8) | pixel_low

                # Map the pixel to an index (0-9)
                index = map_to_index(rgb565)
                if index == 0:
                    index = '.'
                row.append(str(index))

            # Print the row as a table
            print(" ".join(row))

    def debug_pio_fifo(self, pio, sm):
        if pio == 0:
            base_addr = PIO0_BASE
        elif pio == 1:
            base_addr = PIO1_BASE
        else:
            base_addr = PIO2_BASE

        addr = base_addr + FIFO_LEVELS
        value = mem32[addr]
        bin_str = str(f"{value:032b}")

        strTX3 = bin_str[0:4]
        strTX2 = bin_str[8:12]
        strTX1 = bin_str[16:20]
        strTX0 = bin_str[24:28]

        strRX3 = bin_str[4:8]
        strRX2 = bin_str[12:16]
        strRX1 = bin_str[20:24]
        strRX0 = bin_str[28:32]

        print(f"SM       :    0.   1.   2.   3.")
        print(f"-------------------------------")
        print(f"TX LEVELS: {strTX0}-{strTX1}-{strTX2}-{strTX3}")
        print(f"RX LEVELS: {strRX0}-{strRX1}-{strRX2}-{strRX3}")

# Define base types that don't need recursive sizing in MicroPython
# (str, bytes, range, bytearray are handled by getsizeof directly)
ZERO_DEPTH_BASES = (str, bytes, int, float, range, bytearray)

def getsize(obj_0):
    """
    Recursively estimates the memory footprint of an object and its members
    in MicroPython.

    Note: Relies on sys.getsizeof which might reflect block allocation size
    rather than precise content size on some MicroPython ports. The accuracy
    of this function is therefore an ESTIMATE.
    """
    _seen_ids = set() # Keep track of objects already sized to prevent infinite loops

    def inner(obj):
        obj_id = id(obj)
        if obj_id in _seen_ids:
            return 0 # Already counted this object

        _seen_ids.add(obj_id)

        try:
            # Get the base size reported by MicroPython
            size = sys.getsizeof(obj)
        except TypeError:
             # Some objects might not work with getsizeof directly
             print(f"Warning: sys.getsizeof failed for object of type {type(obj)}, using size 0.")
             size = 0


        # --- Check object type and recurse if necessary ---

        if isinstance(obj, ZERO_DEPTH_BASES):
            # For base types, sys.getsizeof is usually sufficient (or the best we can get)
            pass # bypass remaining control flow and return current size

        # --- Container Types ---
        # Note: Removed 'deque' as it's not standard in MicroPython
        elif isinstance(obj, (tuple, list, set)): # Check concrete types
             # Add size of contained items
             size += sum(inner(i) for i in obj)

        elif isinstance(obj, dict): # Check concrete dict type
             # Add size of keys and values
             size += sum(inner(k) + inner(v) for k, v in obj.items())

        # --- Custom Objects ---
        # Check for attributes dictionary
        if hasattr(obj, '__dict__'):
             # Recursively size the dictionary holding instance attributes
             # Note: vars(obj) returns the __dict__ itself
             size += inner(obj.__dict__) # Pass the dict object to inner

        # Check for slots (less common in MP but possible)
        if hasattr(obj, '__slots__'):
             # Recursively size attributes stored in slots
             size += sum(inner(getattr(obj, s)) for s in obj.__slots__ if hasattr(obj, s))

        return size

    # Start the inner recursive function
    return inner(obj_0)

# --- Example Usage ---
# my_list = [1, 2, {"a": 3, "b": [4, 5]}, (6, 7)]
# total_size = getsize(my_list)
# print(f"Estimated size: {total_size} bytes")

# class MyClass:
#     def __init__(self, x, y):
#         self.a = x
#         self.b = y
#         self.c = [x * i for i in range(5)]

# my_obj = MyClass(10, "hello")
# total_size_obj = getsize(my_obj)
# print(f"Estimated size of object: {total_size_obj} bytes")
