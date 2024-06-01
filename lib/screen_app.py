import framebuf
from machine import Pin
import machine
# from ssd1331_16bit import SSD1331
# from ssd_1331 import SSD1331 as Driver
from ssd1331_pio import SSD1331PIO as Driver

class ScreenApp:
    display: framebuf.FrameBuffer
    screens = []
    display: None
    screen_width: int = 0
    screen_height: int = 0

    pin_cs = Pin(1, Pin.OUT)
    pin_sck = Pin(2, Pin.OUT)
    pin_sda = Pin(3, Pin.OUT)
    pin_rst = Pin(4, Pin.OUT, value=0)
    pin_dc = Pin(5, Pin.OUT, value=0)

    def __init__(self, screen_width: int, screen_height: int):
        self.screen_width = screen_width
        self.screen_height = screen_height
        # self.setup_native_display(1, 5, 4, 3, 2)
        self.setup_display()

    def load_screen(self, screen: type):
        screen.app = self
        self.screens.append(screen)

    def run(self):
        for screen in self.screens:
            screen.run()

    def setup_display(self):
        # Pin layout for SSD1331 64x48 OLED display on Raspberry Pi Pico (SPI0)
        # r-pi                  display
        # -----------------------------
        # GPIO1 (SPI0 CS)       CS
        # GPIO2 (SPI0 SCK)      SCL
        # GPIO3 (SPI0 TX)       SDA
        # GPIO4 (or any)        RES
        # GPIO5 (or any)        DC


        spi = machine.SPI(0, baudrate=80_000_000, sck=self.pin_sck, mosi=self.pin_sda, miso=None)
        display = Driver(
            spi,
            self.pin_cs,
            self.pin_dc,
            self.pin_rst,
            height=self.screen_height,
            width=self.screen_width,
            pin_sck=self.pin_sck,
            pin_sda=self.pin_sda)

        # display.set_clock_divide(8)
        self.display = display
        return display

    def setup_native_display(self, pin_cs, pin_dc, pin_rst, pin_sda, pin_sck):
        self.display = Driver(pin_cs, pin_dc, pin_rst, pin_sda, pin_sck)
        self.display.begin(False)
        return self.display

class ScreenAppFramebuf(ScreenApp):
    def __init__(self, screen_height, screen_width):
        self.screen_height = screen_height
        self.screen_width = screen_width

        size = screen_width * screen_height * 2
        self.buffer = bytearray(size)

        self.display = CustomFramebuf(
            self.buffer,
            screen_height,
            screen_width,
            framebuf.RGB565
        )

    def setup_display(self):
        return False

class CustomFramebuf(framebuf.FrameBuffer):
    buffer: None

    def __init__(self, buffer, height, width, format):
        self.buffer = buffer
        super().__init__(buffer, height, width, format)
