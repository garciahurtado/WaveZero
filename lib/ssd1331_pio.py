import framebuf
import utime
from micropython import const
from machine import mem32

from rp2 import PIO, DMA, StateMachine
import rp2
import uctypes
import gc

class SSD1331PIO():
    """ Display driver that uses DMA to transfer bytes from the memory location of a framebuf to the queue of a PIO
    program, which in turn feeds the bits to the SPI pins. This frees the CPU from refreshing the display, and allows
    for much higher framerates than with software refreshes.

    This driver has 2 framebuffers (framebuf):
    - write_buffer: this is the original framebuf from the parent class. We use this for writing to the canvas.
    - read_buffer: this is a new buffer created for the display to read from. This buffer is filled by DMA

    """

    dma0: DMA = None
    dma1: DMA = None
    dma2: DMA = None
    dma0_active = True
    dma1_active = False
    word_size = 4
    dma_tx_count = 256
    buffer0 = None
    buffer1 = None
    framebuf0 = None
    framebuf1 = None
    read_buffer = None
    write_buffer = None
    write_framebuf = None
    read_framebuf = None
    fps = None
    paused = True
    curr_read_addr = False

    HEIGHT: int = const(64)
    WIDTH: int = const(96)
    DMA_BASE = const(0x50000000)
    DC_MODE_CMD = 0x00
    DC_MODE_DATA = 0x01

    """ 
    xA0 x72 -> RGB
    xA0 x76 -> BGR
    """
    INIT_BYTES = b'\xAE\xA0\x76\xA1\x00\xA2\x00\xA4\xA8\x3F\xAD\x8E\xB0'\
                 b'\x0B\xB1\x31\xB3\xF0\x8A\x64\x8B\x78\x8C\x64\xBB\x3A\xBE\x3E\x87'\
                 b'\x06\x81\x91\x82\x50\x83\x7D\xAF'\

    def __init__(self, spi, pin_cs, pin_dc, pin_rs, pin_sck, pin_sda, height=HEIGHT, width=WIDTH):
        self.spi = spi
        self.pin_cs = pin_cs
        self.pin_dc = pin_dc
        self.pin_rs = pin_rs
        self.pin_sck = pin_sck
        self.pin_sda = pin_sda
        self.height = height
        self.width = width

        self.word_size = 4

        mode = framebuf.RGB565
        gc.collect()

        # A second buffer, the read buffer, is the one that gets sent to the display
        # DMA copies the write buffer to this one over time
        self.buffer0 = bytearray(self.height * self.width * 2)  # RGB565 is 2 bytes
        self.framebuf0 = framebuf.FrameBuffer(self.buffer0, self.width, self.height, mode)
        self.framebuf0.fill(0x0)

        # A second buffer, the read buffer, is the one that gets sent to the display
        # DMA copies the write buffer to this one over time
        self.buffer1 = bytearray(self.height * self.width * 2)  # RGB565 is 2 bytes
        self.framebuf1 = framebuf.FrameBuffer(self.buffer1, self.width, self.height, mode)
        self.framebuf1.fill(0x0)

        # Set starting alias to each buffer
        self.write_buffer = self.buffer0
        self.read_buffer = self.buffer1

        self.write_framebuf = self.framebuf0
        self.read_framebuf = self.framebuf1

        self.read_addr = uctypes.addressof(self.read_buffer)
        self.read_addr_buf = self.read_addr.to_bytes(4, "little")

        self.write_addr = uctypes.addressof(self.write_buffer)
        self.write_addr_buf = self.write_addr.to_bytes(4, "little")

        self.curr_read_buf = self.read_addr_buf

    def start(self):
        self.init_display()
        self.init_pio_spi()
        self.init_dma()

    def show(self):
        """ Flip the buffers to make screen refresh faster"""
        self.swap_buffers()

        return

    def swap_buffers(self):
        # if self.paused:
        #     return

        # self.read_buffer, self.write_buffer = self.write_buffer, self.read_buffer
        # self.read_addr, self.write_addr = self.write_addr, self.read_addr
        self.read_addr_buf, self.write_addr_buf = self.write_addr_buf, self.read_addr_buf
        self.read_framebuf, self.write_framebuf = self.write_framebuf, self.read_framebuf

        """ Now that we've flipped the buffers, reprogram the DMA so that it will start reading from the 
        correct buffer (the one that just finished writing) in the next iteration """

        # print(f" <<< SWAPPING BUFFERS >>> addr: {uctypes.addressof(self.read_addr_buf):016X}")

        # mem32[CH1_AL3_READ_ADDR_TRIG] = uctypes.addressof(buf)
        # self.dma1.count = 1

        # read_addr = self.read_addr


        # self.dma1.active(1)

        if self.curr_read_buf == self.read_addr_buf:
            self.curr_read_buf = self.write_addr_buf
        else:
            self.curr_read_buf = self.read_addr_buf

        # self.dma1.read = uctypes.addressof(self.curr_read_buf)

        CH1_AL3_READ_ADDR_TRIG = self.DMA_BASE + (0x040 * self.dma1.channel) + 0x03C
        # mem32[CH1_AL3_READ_ADDR_TRIG] = uctypes.addressof(self.read_addr_buf)

        # The PIO program might be in the middle of a screen refresh, to we need to add the offset it
        # was reading on the old buffer, to the new

        total_bytes = self.height * self.width * 2
        total_tx = int(total_bytes / self.word_size)
        remaining_tx = self.dma0.count
        sent_tx = total_tx - remaining_tx
        sent_bytes = sent_tx * self.word_size
        # self.dma0.active(0)

        new_read_addr = self.read_addr
        # self.read_addr_buf = new_read_addr.to_bytes(4, "little")
        self.dma1.read = uctypes.addressof(self.read_addr_buf)
        self.dma1.count = 1
        self.dma1.active(1)

        # self.paused = True
        # self.debug_dma()

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


    def init_pio_spi(self):
        # Define the pins
        pin_sck = self.pin_sck
        pin_sda = self.pin_sda
        pin_dc = self.pin_dc
        pin_cs = self.pin_cs

        # Set up the PIO state machine
        freq = 120 * 1000 * 1000

        sm = StateMachine(0)

        pin_cs.value(0) # Pull down to enable CS
        pin_dc.value(1) # D/C = 'data'

        sm.init(
            self.dmi_to_spi,
            freq=freq,
            set_base=pin_cs,
            out_base=pin_sda,
            sideset_base=pin_sck,
        )

        # self.sm_debug(sm)
        sm.active(1)

    @rp2.asm_pio(
        out_shiftdir=PIO.SHIFT_LEFT,
        set_init=PIO.OUT_LOW,
        sideset_init=PIO.OUT_LOW,
        out_init=PIO.OUT_LOW
        )

    def dmi_to_spi():
        """This PIO program is in charge for reading from the TX FIFO and writing to the output pin until it runs out
        of data"""
        pull(ifempty, block)       .side(1)     # Block with CSn high (minimum 2 cycles)
        nop()                      .side(0)     # CSn front porch

        set(x, 31)                  .side(1)        # Push out 4 bytes per bitloop
        wrap_target()

        pull(ifempty, block)        .side(1)
        set(pins, 0)                .side(0)  # pull down CS

        label("bitloop")
        out(pins, 1)                .side(0)
        jmp(x_dec, "bitloop")       .side(1)

        set(x, 31)                  .side(1)

        set(pins, 1)                .side(1) # Pulse the CS pin high (set)
        jmp(not_osre, "bitloop")    .side(0) # Fallthru if TXF empties

        nop()                       .side(0)  # CSn back porch

    def sm_debug(self, sm):
        sm.irq(
            lambda pio:
            print(f"IRQ: {pio.irq().flags():08b} - TX fifo size: {sm.tx_fifo()}"))

    def init_dma(self):
        """
        Initialize DMA
            spi0_base = 0x4003c000
            spi0_tx = spi0_base + 0x008
        """
        pio_num = 0 # PIO program number
        sm_num = 0 # State Machine number
        DATA_REQUEST_INDEX = (pio_num << 3) + sm_num
        # DATA_REQUEST_INDEX = 16
        PIO0_BASE = const(0x50200000)
        PIO0_BASE_TXF0 = const(PIO0_BASE + 0x10)

        total_bytes = (self.width * self.height) * 2
        self.dma_tx_count = total_bytes // 4

        # self.debug_dma(buffer_addr, data_bytes)

        # Initialize DMA channels
        self.dma0 = DMA()
        self.dma1 = DMA()
        self.dma2 = DMA()

        # print(f"Start Read Addr: {self.read_addr:032X}")

        """ Data Channel """
        ctrl0 = self.dma0.pack_ctrl(
            size=2,
            inc_read=True,
            inc_write=False,
            irq_quiet=True,
            bswap=True,
            treq_sel=DATA_REQUEST_INDEX
        )
        self.dma0.config(
            count=self.dma_tx_count,
            read=self.read_addr,
            write=PIO0_BASE_TXF0,
            ctrl=ctrl0,
        )

        """ Control Channel """
        ctrl1 = self.dma1.pack_ctrl(
            size=2,
            inc_read=False,
            inc_write=False,
            irq_quiet=True,
            chain_to=self.dma0.channel
        )
        # self.dma1.irq(handler=self.buffer_swap_done, hard=False)

        offset = (0x040 * self.dma0.channel) + 0x03C                #   CH0_AL3_READ_ADDR_TRIG
        dma_read_offset = 0x014                                     #   CH0_AL1_READ_ADDR

        self.dma1.config(
            count=1,
            read=self.read_addr_buf,
            write=self.DMA_BASE,
            ctrl=ctrl1,

        )

        """ Buffer Swap Channel, to be manually triggered as soon as the CPU has finished rendering a frame """
        ctrl2 = self.dma2.pack_ctrl(
            size=2,
            inc_read=True,
            inc_write=True,
            irq_quiet=False,
        )
        self.dma2.config(
            count=self.dma_tx_count,
            read=self.write_addr,
            write=self.read_addr,
            ctrl=ctrl2,
        )
        self.dma2.irq(handler=self.buffer_swap_done)

        """ Kick it off! """
        self.dma0.active(1)
        self.dma0_active = True

    def buffer_swap_done(self, event):
        # print("================= BUFFER SWAP DONE ============")
        self.paused = False
        # self.dma2.read=self.write_addr
        # self.dma2.write=self.read_addr

    def can_write(self):
        return not self.dma2.active()

    """ DRAWING FUNCTIONS """
    def fill(self, color):
        return self.write_framebuf.fill(color)

    def blit(self, pixels, x, y, alpha_idx, palette):
        return self.write_framebuf.blit(pixels, x, y, alpha_idx, palette)

    def rect(self, x, y, width, height, color, fill=None):
        return self.write_framebuf.rect(x, y, width, height, color, fill)

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
