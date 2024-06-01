from ssd1331_16bit import SSD1331
from rp2 import PIO, DMA, StateMachine
import rp2
import uctypes

class SSD1331PIO(SSD1331):
    """ Display driver that uses DMA to transfer bytes from the memory location of a framebuf to the queue of a PIO
    program, which in turn feeds the bits to the SPI pins. This frees the CPU from refreshing the display, and allows
    for much higher framerates than with software refreshes. """

    dma0: DMA = None
    dma1: DMA = None
    dma0_active = True
    dma1_active = False
    word_size = 4
    dma_tx_count = 256
    dma_base = 0x50000000
    buffer = None

    def __init__(self, *args, pin_sck=None, pin_sda=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.pin_sck = pin_sck
        self.pin_sda = pin_sda

    def start(self):
        self.init_pio_spi()
        self.init_dma()

    def show(self):
        """ Since display refresh is via hardware, this becomes a noop"""
        pass

    def init_pio_spi(self):
        # Define the pins
        pin_sck = self.pin_sck
        pin_sda = self.pin_sda
        pin_dc = self._pindc
        pin_cs = self._pincs

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
        out_shiftdir=PIO.SHIFT_RIGHT,
        set_init=PIO.OUT_LOW,
        sideset_init=PIO.OUT_LOW,
        out_init=PIO.OUT_LOW
        )

    def dmi_to_spi():
        """This PIO program is in charge for reading from the TX FIFO and writing to the output pin until it runs out
        of data"""
        pull(ifempty, block)       .side(1) [1]     # Block with CSn high (minimum 2 cycles)
        nop()                      .side(0)     # CSn front porch

        set(x, 15)                  .side(0)        # Push out 4 bytes per bitloop
        wrap_target()

        pull(ifempty, block)        .side(1) [1]
        set(pins, 0)                .side(0) [1] # pull down CS

        label("bitloop")
        out(pins, 1)                .side(1) [1]
        # irq(1)
        jmp(x_dec, "bitloop")       .side(0) [1]

        set(x, 15)                  .side(1)

        set(pins, 1)                .side(1) # Pulse the CS pin high (set)
        nop()                       .side(1)
        jmp(not_osre, "bitloop")    .side(0) [1]  # Fallthru if TXF empties

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
        PIO0_BASE = const(0x50200000)
        PIO0_BASE_TXF0 = const(PIO0_BASE + 0x10)

        self.buffer_addr = uctypes.addressof(self.buffer)
        self.buffer_bytes = int(self.width * self.height * 2)
        print(f"Buffer bytes length: {self.buffer_bytes}")
        self.buffer_end_addr = self.buffer_addr + self.buffer_bytes
        self.dma_tx_count = self.buffer_bytes // 4

        # self.debug_dma(buffer_addr, data_bytes)

        # Initialize DMA channels
        self.dma0 = DMA()
        self.dma1 = DMA()
        ctrl_block = (self.dma_tx_count << 16) | (self.buffer_addr & 0xFFFF)

        """ Control Channel """
        ctrl1 = self.dma1.pack_ctrl(
            size=2,
            inc_read=True,
            inc_write=True,
            irq_quiet=False,
            # ring_size=3,
            # ring_sel=True,
        )
        self.dma1.config(
            count=2,
            read=ctrl_block,
            write=self.dma0.registers[14:16],
            ctrl=ctrl1
        )

        """ Data Channel """
        ctrl0 = self.dma0.pack_ctrl(
            size=0,
            inc_read=True,
            inc_write=False,
            # ring_size=1,
            # ring_sel=False,
            treq_sel=DATA_REQUEST_INDEX,
            chain_to=self.dma1.channel
        )
        self.dma0.config(
            count=self.dma_tx_count,
            read=self.buffer,
            write=PIO0_BASE_TXF0,
            ctrl=ctrl0
        )

        print(f"Channel numbers:")
        print(f" - DMA0: {self.dma0.channel} / DMA1: {self.dma1.channel}")

        self.dma0.irq(handler=self.flip_channels)
        self.dma1.irq(handler=self.flip_channels)

        """ Kick it off! """
        self.dma1.active(1)
        self.dma1_active = True

    def flip_channels(self, event):
        """ Alternate between activating channels 0 and 1 when each finishes their transfers """
        print()
        print("FLIP")
        print()

        if self.dma0.active():
            print("DMA0 active")
            return

            while self.dma0.active():
                pass

            self.dma0_active = False
            self.dma1_active = True

            self.dma1.count = self.dma_tx_count
            self.dma1.active(1)

            if self.dma0.read >= self.buffer_end_addr:
                self.dma0.read = self.buffer_addr

        elif self.dma1.active():
            print("DMA1 active")
            return

            while self.dma1.active():
                pass

            self.dma0_active = True
            self.dma1_active = False

            self.dma1.count = self.dma_tx_count
            self.dma0.active(1)

            if self.dma1.read >= self.buffer_end_addr:
                self.dma1.read = self.buffer_addr

        # print("Channel 0 details:")
        # print(DMA.unpack_ctrl(self.dma0.ctrl))
        # print("Channel 1 details:")
        # print(DMA.unpack_ctrl(self.dma1.ctrl))
        # print(f"DMA act.: dma0:{self.dma0.active()} dma1:{self.dma1.active()}")

