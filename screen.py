import asyncio

import framebuf
import machine
from machine import Pin

from fps_counter import FpsCounter
from lib.ssd1331_16bit import SSD1331 as SSD
from ui_elements import ui


class Screen:
    display:framebuf.FrameBuffer
    screen:ui

    def __init__(self):
        self.setup_display()
        self.screen = ui(self.display)
        self.fps = FpsCounter()

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
        ssd = SSD(spi, pin_cs, pin_dc, pin_rst, height=64, width=96)  # Create a display instance

        self.display = ssd
        return ssd

    async def refresh(self):
        while True:
            self.display.show()
            self.fps.tick()
            await asyncio.sleep(0.02)

    def refresh_display(self):
        self.screen.draw_sprites()
        self.display.show()
        self.fps.tick()