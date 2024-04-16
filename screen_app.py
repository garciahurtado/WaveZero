import asyncio

import framebuf
from machine import Pin
import machine
from lib.ssd1331_16bit import SSD1331 as SSD


class ScreenApp:
    display: framebuf.FrameBuffer
    screens = []

    def __init__(self, screen_width, screen_height):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.setup_display()

    def load_screen(self, screen: type):
        screen.__init__(self.display)
        self.screens.append(screen)

    def run(self):
        for screen in self.screens:
            screen.run()

    def setup_display(self):
        # Pin layout for SSD1331 64x48 OLED display on Raspberry Pi Pico (SPI0)
        # GPIO1 (SPI0 CS)       CS
        # GPIO2 (SPI0 SCK)      SCL
        # GPIO3 (SPI0 TX)       SDA
        # GPIO4 (or any)        RES
        # GPIO5 (or any)        DC

        pin_cs = Pin(1, Pin.OUT)
        pin_sck = Pin(2, Pin.OUT)
        pin_sda = Pin(3, Pin.OUT)
        pin_rst = Pin(4, Pin.OUT, value=0)
        pin_dc = Pin(5, Pin.OUT, value=0)

        spi = machine.SPI(0, baudrate=24_000_000, sck=pin_sck, mosi=pin_sda, miso=None)
        ssd = SSD(spi, pin_cs, pin_dc, pin_rst, height=self.screen_height,
                  width=self.screen_width)  # Create a display instance

        self.display = ssd
        return ssd
