from machine import Pin, SPI
from ssd1331_pio import SSD1331PIO as DisplayDriver
import utime

# display = None # Global display variable, so we can make a singleton

def get_display():
    display = setup_display()
    return display

def setup_display():
    # Pin layout for SSD1331 64x48 OLED display on Raspberry Pi Pico (SPI0)
    # r-pi                  display
    # -----------------------------
    # GPIO1 (SPI0 CS)       CS
    # GPIO2 (SPI0 SCK)      SCL
    # GPIO3 (SPI0 TX)       SDA
    # GPIO4 (or any)        RES
    # GPIO5 (or any)        DC

    screen_width = 96
    screen_height = 64

    pin_cs = Pin(1, Pin.OUT)
    pin_sck = Pin(2, Pin.OUT)
    pin_sda = Pin(3, Pin.OUT)
    pin_rst = Pin(4, Pin.OUT, value=0)
    pin_dc = Pin(5, Pin.OUT, value=0)

    utime.sleep_ms(100)

    spi = SPI(0, baudrate=12_000_000, sck=pin_sck, mosi=pin_sda, miso=None)
    display = DisplayDriver(
        spi,
        pin_cs,
        pin_dc,
        pin_rst,
        height=screen_height,
        width=screen_width,
        pin_sck=pin_sck,
        pin_sda=pin_sda)

    display.start()
    return display
