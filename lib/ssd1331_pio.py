import framebuf

from ssd1331_16bit import SSD1331
from rp2 import PIO, DMA, StateMachine
import rp2
import uctypes
import gc

class SSD1331PIO(SSD1331):
    """ Display driver that uses DMA to transfer bytes from the memory location of a framebuf to the queue of a PIO
    program, which in turn feeds the bits to the SPI pins. This frees the CPU from refreshing the display, and allows
    for much higher framerates than with software refreshes. """

    dma0: DMA = None
    dma1: DMA = None
    dma2: DMA = None
    dma0_active = True
    dma1_active = False
    word_size = 4
    dma_tx_count = 256
    dma_base = 0x50000000
    buffer = None
    read_buffer = None
    read_framebuf = None
    fps = None
    paused = True

    def __init__(self, *args, pin_sck=None, pin_sda=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.pin_sck = pin_sck
        self.pin_sda = pin_sda

        """ Create a second screen buffer to reduce flicker """
        mode = framebuf.RGB565
        gc.collect()
        self.write_buffer = bytearray(self.height * self.width * 2)  # RGB565 is 2 bytes
        self.write_framebuf = framebuf.FrameBuffer(self.write_buffer, self.width, self.height, mode)
        self.write_framebuf.fill(0x0)
        self.read_buffer = self.buffer

    def start(self):
        super().show()

        self.init_pio_spi()
        self.init_dma()
        self.paused = False

    def show(self):
        """ Flip the buffers to make screen refresh faster"""
        if self.paused:
            return

        self.paused = True
        self.do_swap()

        """ Wait until DMA transfer is done"""
        while self.paused:
            pass

        return

    def init_pio_spi(self):
        # Define the pins
        pin_sck = self.pin_sck
        pin_sda = self.pin_sda
        pin_dc = self._pindc
        pin_cs = self._pincs

        # Set up the PIO state machine
        freq = 20 * 1000 * 1000

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
        pull(ifempty, block)       .side(1) [1]     # Block with CSn high (minimum 2 cycles)
        nop()                      .side(0)     # CSn front porch

        set(x, 31)                  .side(0)        # Push out 4 bytes per bitloop
        wrap_target()

        pull(ifempty, block)        .side(1)
        set(pins, 0)                .side(0)  # pull down CS

        label("bitloop")
        out(pins, 1)                .side(1)
        # irq(1)
        jmp(x_dec, "bitloop")       .side(0)

        set(x, 31)                  .side(1)

        set(pins, 1)                .side(1) # Pulse the CS pin high (set)
        jmp(not_osre, "bitloop")    .side(0) # Fallthru if TXF empties

        # irq(1)                      .side(0)
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
        word_size = self.word_size

        dma0_reg = self.dma_base + 0x038 # Point to the CH0_AL3_TRANS_COUNT register, which will trigger the channel

        pio_num = 0 # PIO program number
        sm_num = 0 # State Machine number
        DATA_REQUEST_INDEX = (pio_num << 3) + sm_num
        # DATA_REQUEST_INDEX = 16
        DMA_BASE = const(0x50000000)
        PIO0_BASE = const(0x50200000)
        PIO0_BASE_TXF0 = const(PIO0_BASE + 0x10)

        self.buffer_addr = uctypes.addressof(self.read_buffer)

        self.read_addr = uctypes.addressof(self.buffer)
        self.write_addr = uctypes.addressof(self.write_buffer)

        self.buffer_bytes = int(self.width * self.height * 2)
        print(f"Buffer bytes length: {self.buffer_bytes}")
        # self.buffer_end_addr = self.buffer_addr + self.buffer_bytes

        total_bytes = (self.width * self.height) * 2
        self.dma_tx_count = total_bytes // 4
        print(f"TX count: {self.dma_tx_count}")

        # self.debug_dma(buffer_addr, data_bytes)

        # Initialize DMA channels
        self.dma0 = DMA()
        self.dma1 = DMA()
        self.dma2 = DMA()

        buf = bytes(self.buffer_addr.to_bytes(4, "little"))
        self.ctrl_block = bytearray(buf)
        int_buf = int.from_bytes(self.ctrl_block, "little")

        print(f"CTRL: {int_buf:016X}")
        # self.ctrl_block = bytearray((self.dma_tx_count << 32) | (self.buffer_addr & 0xFFFFFFFF))
        self.ctrl_size = 2 # 4 bytes

        print(f"Start Read Addr: {self.buffer_addr:032X}")

        """ Data Channel """
        ctrl0 = self.dma0.pack_ctrl(
            size=2,
            inc_read=True,
            inc_write=False,
            irq_quiet=True,
            treq_sel=DATA_REQUEST_INDEX,
            chain_to=self.dma1.channel
        )
        self.dma0.config(
            count=self.dma_tx_count,
            read=self.write_addr,
            write=PIO0_BASE_TXF0,
            ctrl=ctrl0
        )

        """ Control Channel """
        ctrl1 = self.dma1.pack_ctrl(
            size=self.ctrl_size,
            inc_read=False,
            inc_write=False,
            irq_quiet=True,
            chain_to=self.dma2.channel
        )
        self.dma1.config(
            count=1,
            read=uctypes.addressof(self.ctrl_block),
            write=DMA_BASE + 0x03C, # self.dma0.registers[14] / CH0_AL3_READ_ADDR_TRIG
            ctrl=ctrl1,
        )
        # self.dma1.irq(handler=self.restart_channels)

        """ Buffer Swap Channel, to be triggered as soon as the CPU has finished rendering a frame """
        ctrl2 = self.dma2.pack_ctrl(
            size=2,
            inc_read=True,
            inc_write=True,
            irq_quiet=False,
        )
        self.dma2.config(
            count=self.dma_tx_count,
            read=self.read_addr,
            write=self.write_addr,
            ctrl=ctrl2,
        )
        self.dma2.irq(handler=self.buffer_swap_done)
        # self.dma0.irq(handler=self.flip_channels)

        """ Kick it off! """
        self.dma0.active(0)
        self.dma0.active(1)
        self.dma0_active = True


    def buffer_swap_done(self, event):
        self.dma2.read=uctypes.addressof(self.read_buffer)
        self.dma2.write=self.write_addr
        self.dma2.count = self.dma_tx_count
        self.paused = False

    def restart_channels(self, event):
        print("Channel restart -- ")
        """ First of all, flip the buffers"""
        # self.debug_dma()

        # if self.buffer_addr == uctypes.addressof(self.read_buffer):
        #     tmp = self.buffer_addr
        #     self.buffer_addr = uctypes.addressof(self.write_buffer)
        #     self.read_buffer = tmp
        # else:
        #     tmp = self.buffer_addr
        #     self.buffer_addr = uctypes.addressof(self.read_buffer)
        #     self.write_buffer = tmp
        self.fps.tick()

        # print("Frame complete. Restarting DMA channels...")
        # self.buffer = self.read_buffer
        self.dma0.count = self.dma_tx_count
        self.dma0.read = self.buffer_addr
        # self.dma1.count = self.ctrl_count
        # self.dma1.read = self.ctrl_block
        self.dma0.active(1)
        pass

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
        print("DMA DEBUG --------------------------")

    def debug_buffer(self, buffer_addr, data_bytes):
        print(f"Framebuf addr: {buffer_addr:16x} / len: {len(data_bytes)}")
        print(f"Contents: ")

        for i in range(64):
            my_str = ''
            for i in range(0, 32, 1):
                my_str += f"{data_bytes[i]:02x}"

            print(my_str)
