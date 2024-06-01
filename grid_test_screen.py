import gc
import random

from micropython import const
import _thread
from machine import mem32, Pin
import rp2
from rp2 import PIO, DMA

from perspective_camera import PerspectiveCamera
from screen import Screen
from road_grid import RoadGrid
import asyncio
import utime
import uctypes
import machine

class GridTestScreen(Screen):
    lane_width: int = const(24)
    ground_speed: int = const(50)
    grid: RoadGrid = None
    camera: PerspectiveCamera
    sprites: []
    sprite_max_z: int = const(1301)
    ground_speed = 1000
    ground_max_speed: int = const(300)
    saved_ground_speed = 0
    lane_width: int = const(24)
    num_lives: int = const(4)
    crash_y_start = const(48)  # Screen Y of Sprites which will collide with the player
    crash_y_end = const(62)  # Screen Y of end collision
    total_frames = 0

    dma0: DMA = None
    dma1: DMA = None
    dma_out_pin = None
    dma0_active = True
    dma1_active = False
    dma_tx_count = 64

    def __init__(self, display, *args, **kwargs):
        super().__init__(display, *args, **kwargs)

        self.init_camera()

        """ Display Thread / 2nd core """

    def run(self):

        print("-- Creating road grid...")

        self.grid = RoadGrid(self.camera, self.display, lane_width=self.lane_width)
        self.grid.speed = self.ground_speed

        # led = Pin(25, Pin.OUT)
        #
        self.display.fill(0xFFFF)
        self.display.show()

        utime.sleep_ms(1000)
        self.display.fill(0x00FF)
        self.init_pio_spi()

        self.init_dma()
        self.dma0.active(0)
        self.dma0.active(1)
        self.dma0_active = True

        print("-- DMA Initialized")

        asyncio.run(self.main_loop())

    @rp2.asm_pio(
        out_shiftdir=PIO.SHIFT_LEFT,
        set_init=PIO.OUT_LOW,
        sideset_init=rp2.PIO.OUT_LOW,
        out_init=rp2.PIO.OUT_LOW
        )
    def dmi_to_spi():
        """This PIO program is in charge for reading from the FIFO and writing to the output pin until it runs out
        of data"""
        pull(ifempty, block)       .side(1) [1]     # Block with CSn high (minimum 2 cycles)
        nop()                      .side(0) [1]     # CSn front porch

        set(x, 31)                  .side(0)        # Push out 4 bytes per bitloop
        wrap_target()

        pull(ifempty, block)        .side(1) [1]
        set(pins, 0)                .side(0) # pull down CS

        label("bitloop")
        out(pins, 1)                .side(1)
        # irq(1)
        jmp(x_dec, "bitloop")       .side(0)

        set(x, 31)                  .side(0)

        set(pins, 1)                .side(1) # Pulse the CS pin high (set)
        nop()                       .side(1)
        jmp(not_osre, "bitloop")    .side(0) [1]  # Fallthru if TXF empties

        # irq(1)                      .side(0)
        nop()                       .side(0)  # CSn back porch

        # Define the second PIO program
    @rp2.asm_pio(set_init=PIO.OUT_LOW,  sideset_init=PIO.OUT_LOW, in_shiftdir=PIO.SHIFT_LEFT, out_shiftdir = PIO.SHIFT_RIGHT)
    def spi_cpha1_cs():
        label("bitloop")
        out(pins, 32)                   .side(0x1)[1]
        in_(pins, 32)
        jmp(x_dec, "bitloop")           .side(0x0)

        out(pins, 32)                   .side(0x1)
        mov(x, y)                       .side(0x1)
        in_(pins, 32)
        jmp(not_osre, "bitloop")        .side(0x0)

        label("entry_point")
        pull(ifempty, block)            .side(0x2)[1]
        nop()                           .side(0x0)[1]

    def init_pio_spi(self):
        print(self.app.pin_cs)

        # Define the pins
        pin_cs = self.app.pin_cs
        pin_sck = self.app.pin_sck
        pin_sda = self.app.pin_sda
        pin_rst = self.app.pin_rst
        pin_dc = self.app.pin_dc

        # Set up the PIO state machine
        freq = 120 * 1000 * 1000
        sm = rp2.StateMachine(0)

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
        PIO0_BASE = const(0x50200000)
        PIO0_BASE_TXF0 = const(PIO0_BASE + 0x10)

        data_bytes = self.display.buffer
        self.buffer_addr = uctypes.addressof(data_bytes)
        self.end_addr = self.buffer_addr + (self.display.width * self.display.height * 2)
        # self.debug_dma(buffer_addr, data_bytes)

        # Initialize DMA channels
        self.dma0 = DMA()
        self.dma1 = DMA()

        # Configure DMA channels
        ctrl0 = self.dma0.pack_ctrl(
            size=2,
            inc_read=True,
            inc_write=False,
            irq_quiet=False,
            treq_sel=DATA_REQUEST_INDEX,
        )

        ctrl1 = self.dma1.pack_ctrl(
            size=2,
            inc_read=True,
            inc_write=False,
            irq_quiet=False,
            treq_sel=DATA_REQUEST_INDEX,
        )

        self.dma0.irq(handler=self.flip_channels)
        self.dma1.irq(handler=self.flip_channels)

        self.dma0.config(
            read=data_bytes,
            write=PIO0_BASE_TXF0,
            count=self.dma_tx_count,
            ctrl=ctrl0
        )

        self.dma1.config(
            read=data_bytes,
            write=PIO0_BASE_TXF0,
            count=self.dma_tx_count,
            ctrl=ctrl1
        )

    def flip_channels(self, event):
        """ Alternate between activating channels 0 and 1 when each finishes their transfers """

        if self.dma0_active:
            while self.dma0.active():
                pass

            self.dma0_active = False
            self.dma1_active = True

            self.dma1.count = self.dma_tx_count
            self.dma1.active(1)

            if self.dma0.read > self.end_addr:
                self.fps.tick()
                self.dma0.read = self.buffer_addr

        else:
            while self.dma1.active():
                pass

            self.dma0_active = True
            self.dma1_active = False

            self.dma1.count = self.dma_tx_count
            self.dma0.active(1)

            if self.dma1.read > self.end_addr:
                self.dma1.read = self.buffer_addr

        # print("Channel 0 details:")
        # print(DMA.unpack_ctrl(self.dma0.ctrl))
        # print("Channel 1 details:")
        # print(DMA.unpack_ctrl(self.dma1.ctrl))
        # print(f"DMA act.: dma0:{self.dma0.active()} dma1:{self.dma1.active()}")


    def start_display_loop(self):
        # Start display and input
        loop = asyncio.get_event_loop()
        self.display_task = loop.create_task(self.refresh_display())

    async def main_loop(self):
        await asyncio.gather(
            self.update_loop(),
            # self.update_fps(),
        )

    async def update_loop(self):
        start_time_ms = round(utime.ticks_ms())
        print(f"Update loop Start time: {start_time_ms}")
        self.check_mem()

        # update loop - will run until task cancellation
        try:
            while True:
                # gc.collect()
                self.grid.speed = self.ground_speed
                self.total_frames += 1
                fps_every_n_frames = 100
                color_shift_every_n_frames = 10

                if not self.total_frames % fps_every_n_frames:
                    print(f"FPS: {self.fps.fps()}")

                if not self.total_frames % color_shift_every_n_frames:
                    color_a = int(random.randrange(0,255)) * 255
                    color_b = random.randrange(0,255)
                    color = color_a + color_b
                    # print(f"Change color to {color}")
                    self.display.fill(int(color))

                await asyncio.sleep(1/200)

        except asyncio.CancelledError:
            return False

    def do_refresh(self):
        """ Overrides parent method """
        # self.display.fill(0xFFFF)
        # self.grid.show()
        utime.sleep_ms(30)

        # self.display.show()
        self.fps.tick()

    def init_camera(self):
        # Camera
        horiz_y: int = 16
        camera_z: int = 64
        self.camera = PerspectiveCamera(
            self.display,
            pos_x=0,
            pos_y=54,
            pos_z=-camera_z,
            focal_length=camera_z,
            vp_x=0,
            vp_y=horiz_y+2)
        self.camera.horiz_z = self.sprite_max_z

    def debug_dma(self, buffer_addr, data_bytes):
        print(f"Framebuf addr: {buffer_addr:16x} / len: {len(data_bytes)}")
        print(f"Contents: ")

        for i in range(64):
            my_str = ''
            for i in range(0, 32, 1):
                my_str += f"{data_bytes[i]:02x}"

            print(my_str)


