import _thread
import struct

import framebuf
import math

import time
import utime
from array import array
from machine import mem32
from micropython import const

from rp2 import PIO, DMA, StateMachine
import rp2
import uctypes
from uctypes import addressof
import gc
import colors.color_util as colors
from scaler.status_leds import get_status_led_obj
from scaler.const import DEBUG_DMA, DMA_BASE_1, DMA_READ_ADDR_TRIG, DMA_WRITE_ADDR_TRIG, DMA_READ_ADDR, PIO0_BASE, \
    PIO1_BASE, PIO0_TX0, PIO0_CTRL, DMA_BASE, DEBUG_DISPLAY, DMA_TRANS_COUNT, DREQ_PIO0_TX0, MULTI_CHAN_TRIGGER, \
    PIO0_SM0_SHIFTCTRL, DEBUG_PIO, DMA_WRITE_ADDR, DEBUG_IRQ, DMA_BASE_8, DMA_BASE_7, DEBUG_LED, DMA_BASE_0
from utils import aligned_buffer

class SSD1331PIO():
    """ Display driver that uses DMA to transfer bytes from the memory location of a framebuf to the queue of a PIO
    program, which in turn feeds the bits to the SPI pins. This frees the CPU from refreshing the display, and allows
    for much higher framerates than with software refreshes.

    This driver has 2 framebuffers (framebuf):
    - write_buffer: this is the original framebuf from the parent class. We use this for writing to the canvas.
    - read_buffer: this is a new buffer created for the display to read from. This buffer is filled by DMA

    Inspired by:
    https://github.com/stienman/Raspberry-Pi-Pico-PIO-LCD-Driver
    https://github.com/messani/pico-hd44780/blob/main/pio_hd44780.pio
    https://github.com/sumotoy/SSD_13XX/blob/master/_includes/SSD_1331_registers.h
    https://github.com/WolfWings/SSD1331_t3/blob/master/SSD1331_t3.cpp
    https://github.com/robert-hh/SSD1963-TFT-Library-for-PyBoard-and-RP2040/blob/master/rp2040/tft_pio.py
    https://github.com/ohmytime/TFT_eSPI_DynamicSpeed

    """
    HEIGHT: int = const(64)
    WIDTH: int = const(96)
    DC_MODE_CMD = 0x00
    DC_MODE_DATA = 0x01

    dma0: DMA = None
    dma1: DMA = None

    sm = None
    flip = False
    flop = not flip

    buffer0 = aligned_buffer(HEIGHT * WIDTH * 2)  # RGB565 is 2 bytes per px
    buffer1 = aligned_buffer(HEIGHT * WIDTH * 2)

    dma_tx_count = 0

    fps = None
    paused = True

    """ 
    xA0 x72 -> RGB
    xA0 x76 -> BGR
    """

    status_led = None

    INIT_BYTES = (
        b'\xAE'  # Set Display Off (turn off display during initialization)
        b'\xA0\x76'  # Set Remap/Color Depth: Horizontal address increment, column remap, nibble remap, vertical increment, COM split, 65k color depth (16-bit)
        b'\xA1\x00'  # Set Display Start Line: Start at line 0
        b'\xA2\x00'  # Set Display Offset: No offset
        b'\xA4'      # Set Display Mode: Normal Display (not all pixels on/off)
        b'\xA8\x3F'  # Set Multiplex Ratio: 64 COM lines (0x3F = 63 for 64 rows)
        b'\xAD\x8E'  # Set Master Configuration: Enable internal VCC regulator, default settings
        b'\xB0\x0B'  # Set Power Save Mode: Disabled
        b'\xB1\x31'  # Set Phase 1 and 2 Periods: Phase 1 = 3 DCLKs, Phase 2 = 1 DCLK
        b'\xB3\xF0'  # Set Display Clock Divide Ratio/Oscillator Frequency: Divide Ratio = 0x0, Oscillator Frequency = 0xF (max)
        b'\x8A\x64'  # Set Second Pre-Charge Period: 100 us
        b'\x8B\x78'  # Set Pre-Charge Voltage: Default
        b'\x8C\x64'  # Set VCOMH Deselect Level: Default
        b'\xBB\x3A'  # Set Pre-Charge Period: Default
        b'\xBE\x3E'  # Set VSL (Voltage Supply Level): Default
        b'\x87\x06'  # Set Master Current Control: Default
        b'\x81\x91'  # Set Contrast for Color A (Red): Default
        b'\x82\x50'  # Set Contrast for Color B (Green): Default
        b'\x83\x7D'  # Set Contrast for Color C (Blue): Default
        b'\xAF'  # Set Display On (turn on display after initialization)
    )

    def __init__(self, spi, pin_cs, pin_dc, pin_rs, pin_sck, pin_sda, height=HEIGHT, width=WIDTH):
        self.spi = spi
        self.pin_cs = pin_cs
        self.pin_dc = pin_dc
        self.pin_rs = pin_rs
        self.pin_sck = pin_sck
        self.pin_sda = pin_sda
        self.height = height
        self.width = width

        self.status_led = get_status_led_obj()

        # Initialize DMA channels
        self.dma0 = DMA()
        self.dma1 = DMA()

        self.flip = False

        if DEBUG_DMA:
            addr0 = addressof(self.buffer0)
            addr1 = addressof(self.buffer1)
            print(f" > BUFFER 0 ADDR: 0x{addr0:08X}")
            print(f" > BUFFER 1 ADDR: 0x{addr1:08X}")

        self.is_render_done = False
        self.is_render_ctrl_done = False

        mode = framebuf.RGB565
        gc.collect()

        # Buffer #1: the one we write to
        self.framebuf0 = framebuf.FrameBuffer(self.buffer0, self.WIDTH, self.HEIGHT, mode)
        self.framebuf0.fill(0x0)

        # Buffer #2: the one we read from, is the one that gets sent to the display
        # DMA copies the write buffer to this one when the writing finishes
        self.framebuf1 = framebuf.FrameBuffer(self.buffer1, self.WIDTH, self.HEIGHT, mode)
        self.framebuf1.fill(colors.hex_to_565(0x0B0B0B))

        # Set starting alias to each framebuffer, just to make it clear that they will swap places
        # framebuf0 -> buffer0
        # framebuf1 -> buffer1

        self.write_framebuf = self.framebuf0
        self.read_framebuf = self.framebuf1

        self.buffer0_addr = int(addressof(self.buffer0))
        self.buffer0_addr_buf = self.buffer0_addr.to_bytes(4, "little")

        self.buffer1_addr = int(addressof(self.buffer1))
        self.buffer1_addr_buf = self.buffer1_addr.to_bytes(4, "little")

    def start(self):
        self.init_display()
        self.init_dma()
        self.init_pio_spi()

        """ Kick it off! """
        # self.dma1.active(1)

    def show(self):
        """
        Swaps the framebuffers to prepare for rendering the next frame.

        The DMA channel responsible for pushing data to the display always reads from the 'read' framebuffer.
        By swapping the buffers, the 'read' framebuffer becomes the newly rendered frame, and the 'write' framebuffer
        becomes available for the next frame to be drawn. This effectively triggers the rendering of a new frame.
        """
        self.swap_buffers()
        return

    def swap_buffers(self):
        if DEBUG_DISPLAY:
            print()
            print(">> 1. About to swap buffers <<")

        while self.dma0.active():
            utime.sleep_ms(1)

        self.is_render_done = False

        # Use the trigger register so we dont have to kick off the DMA1 after reconfig
        dma1_read_trigger = DMA_BASE_1 + DMA_READ_ADDR_TRIG

        """ Reconfigure the control channel read to point to the other buffer """
        if self.flip:
            self.read_framebuf = self.framebuf1
            self.write_framebuf = self.framebuf0
            which_addr = addressof(self.buffer1_addr_buf)
            self.flip = False
        else:
            self.read_framebuf = self.framebuf0
            self.write_framebuf = self.framebuf1
            which_addr = addressof(self.buffer0_addr_buf)
            self.flip = True

        sent_to_dma0 = mem32[which_addr]
        mem32[dma1_read_trigger] = which_addr

        if DEBUG_DISPLAY:
            print(">> 2. Active render is done <<")

        if DEBUG_DISPLAY:
            dma0_read = self.dma0.read
            dma1_read_addr = self.dma1.read

            print(">> ------ BUFFERS SWAPPED ------ <<")
            print(f"--- DMA0 READ: 0x{sent_to_dma0:08X} (in progress)")
            print(f"--- DMA1 READ: 0x{dma1_read_addr:08X} (next)")



    def init_display(self):
        self.pin_rs(0)  # Pulse the reset line
        utime.sleep_ms(1)
        self.pin_rs(1)
        utime.sleep_ms(1)

        self.pin_cs(1)
        self.pin_dc(self.DC_MODE_CMD)
        self.pin_cs(0)
        self.spi.write(self.INIT_BYTES)
        self.pin_cs(1)
        self.pin_dc(self.DC_MODE_DATA)

    def direct_hline(self, y, color):
        """ Draw a line directly onto the display using the graphics acceleration commands
        """
        x0 = 0
        x1 = self.width
        y0 = y1 = y

        start_line = b'\x21'

        self.pin_cs(1)
        self.pin_dc(self.DC_MODE_CMD)
        self.pin_cs(0)
        self.spi.write(start_line)
        self.pin_cs(1)
        self.pin_dc(self.DC_MODE_DATA)
        self.pin_cs(0)

        # Testing SPI with some green dots
        # coords = bytes([int(x0), int(y0), int(x1), int(y1)])
        # color = b'\xFF\xFF'
        # self.spi.write(coords)
        # self.spi.write(color)

        # Return to data mode
        self.pin_cs(1)
        self.pin_dc(self.DC_MODE_DATA)

    def init_pio_spi(self, freq=64_000_000):
        """"""
        # Define the SPI pins
        pin_sck = self.pin_sck
        pin_sda = self.pin_sda
        pin_dc = self.pin_dc
        pin_cs = self.pin_cs

        pin_cs.value(0) # Pull down to enable CS
        pin_dc.value(1) # D/C = 'data'

        # Set up the PIO state machine
        sm = StateMachine(0)
        sm.init(
            self.pixels_to_spi,
            freq=freq,
            out_base=pin_sda,
            set_base=pin_cs,
            sideset_base=pin_sck,
        )

        # merge both FIFOS
        addr = PIO0_SM0_SHIFTCTRL
        current = mem32[addr]
        current = current | (1<<30)
        mem32[addr] = current

        self.is_spi_done = False
        sm.active(1)
        self.sm = sm

    @rp2.asm_pio(
        out_shiftdir=PIO.SHIFT_LEFT,
        set_init=PIO.OUT_LOW,
        sideset_init=PIO.OUT_HIGH,
        out_init=PIO.OUT_LOW,
        pull_thresh=32
        )

    def pixels_to_spi():
        """This PIO program is in charge for reading from the TX FIFO and writing to the output pin of the display
        until it runs out of data in the queue"""
        """
        set()   -> pin.cs
        .side() -> pin.sck
        """
        label("start")
        set(pins, 1)
        nop()             [1].side(1)     # Block with CSn high (minimum 2 cycles)
        nop()                               .side(0)      # CSn front porch
        nop()                         .side(0)     # Push out 4 bytes per bitloop

        label("wrap_target")
        wrap_target()
        set(x, 31)

        pull(block)                 .side(1)
        set(pins, 0)                .side(1)  # pull down CS, SCK low

        label("bitloop")
        out(pins, 1)              [1]  .side(0)
        jmp(x_dec, "bitloop")     [1]  .side(1)

        nop()                .side(0) # 1 bit was already transmited
        set(pins, 1)                .side(0) # CS pin high (end transaction)

        jmp(not_osre, "bitloop") [1] .side(1)  # If more data, do next block
        nop()                    [1] .side(0)  # CSn back porch

        # -- Check if FIFO empty
        mov(y, status)  # status will be all 1s when FIFO TX level = 0 (n < 1), and 0s otherwise
        jmp(invert(not_y), "wrap_target")  # Its NOT empty, which means we can do another pull, lets jump
        jmp("start")

    def init_dma(self):
        """
        One time initialization of DMA
        """

        if DEBUG_DMA:
            print(" - SSD1331 PIO Driver. Acquired DMA channels:")
            print(f"   * DMA0 (CH:{self.dma0.channel})")
            print(f"   * DMA1 (CH:{self.dma1.channel})")

        """
        How many bytes to write for a whole framebuffer:
         width * height = pixels
         pixels * 2 = bytes (2 bytes per px)
         bytes / 4 = total tx (at 4 bytes per tx, ie: 32bit)
        """
        self.total_bytes = (self.width * self.height) * 2
        self.dma_tx_count = self.total_bytes // 4

        if DEBUG_DMA:
            print(f" Start Read Addr: {addressof(self.buffer0):08X}")
            print(f" No. DMA0 TX:     {self.dma_tx_count}")
            print(" ........................................")

        """ Data Channel """
        ctrl0 = self.dma0.pack_ctrl(
            size=2,
            inc_read=True,
            inc_write=False,
            bswap=True,
            treq_sel=DREQ_PIO0_TX0,
            irq_quiet=True,
            chain_to=self.dma0.channel # No chain
        )
        self.dma0.config(
            count=self.dma_tx_count,
            read=0,
            write=PIO0_TX0,
            ctrl=ctrl0,
        )
        # self.dma0.irq(handler=self.irq_render)

        """ Control Channel """
        ctrl1 = self.dma1.pack_ctrl(
            size=2,
            inc_read=False,
            inc_write=False,
        )

        self.dma1.config(
            count=1,
            read=0,
            write=DMA_BASE + DMA_READ_ADDR_TRIG,
            ctrl=ctrl1,
        )

    def irq_render(self, dma):
        self.is_render_done = True

        if DEBUG_LED and self.status_led:
            self.status_led.blink_led(1)

        if DEBUG_IRQ:
            print(f"===== [IRQ] RENDER DONE (TX count: {self.dma0.count} - \tch:{dma.channel})=====")

    def irq_render_ctrl(self, dma):
        self.is_render_ctrl_done = True

        if DEBUG_LED and self.status_led:
            self.status_led.blink_led(2)

        if DEBUG_IRQ:
            print(f"<<<<< [IRQ] RENDER CTRL DONE - ch:{dma.channel} >>>>>")

    """ DRAWING FUNCTIONS """
    def pixel(self, x, y, color=None):
        if color:
            return self.write_framebuf.pixel(x, y, color)
        else:
            return self.write_framebuf.pixel(x, y)

    def fill(self, color):
        return self.write_framebuf.fill(color)

    def blit(self, pixels, x, y, alpha_idx=-1, palette=None):
        return self.write_framebuf.blit(pixels, x, y, alpha_idx, palette)

    def rect(self, x, y, width, height, color, fill=None):
        return self.write_framebuf.rect(x, y, width, height, color, fill)

    """ adapter to work with the software driver """
    def fill_rect(self, x, y, width, height, color):
        return self.write_framebuf.fill_rect(x, y, width, height, color)

    def hline(self, x, y, width, color):
        # print(f"hline color: {color:04X}")
        return self.write_framebuf.hline(x, y, width, color)

    def line(self, x1, y1, x2, y2, color):
        return self.write_framebuf.line(x1, y1, x2, y2, color)

    def debug_dma(self):
        channels = [self.dma0, self.dma1]
        print("DMA DEBUG --------------------------")
        for ch in channels:
            print(f".DMA Chan. #:{ch.channel}")
            print(f"  active    :{ch.active()}")
            print(f"  tx.       :{ch.count}")
            print(f"  read add. :0x{ch.read:010X}")
            print(f"  write add.:0x{ch.write:010X}")
            print()

    def debug_buffer(self, buffer_addr, data_bytes):
        print(f"Framebuf addr: {buffer_addr:16x} / len: {len(data_bytes)}")
        print(f"Contents: ")

        for i in range(64):
            my_str = ''
            for i in range(0, 32, 1):
                my_str += f"{data_bytes[i]:02x}"

            print(my_str)
