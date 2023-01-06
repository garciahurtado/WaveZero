import adafruit_framebuf as framebuf
import busio
import board
import displayio


from adafruit_ssd1331 import SSD1331


class SSD1331Display(SSD1331):
    screen_width = 96
    screen_height = 64

    # Pin layout for SSD1331 64x48 OLED display on Raspberry Pi Pico
    oled_dc = board.GP16
    oled_cs = board.GP17
    oled_sda = board.GP3
    oled_scl = board.GP2
    oled_res = board.GP20
    
    def __init__(self, *args, **kwargs):
        displayio.release_displays()

        spi = busio.SPI(self.oled_scl, self.oled_sda)
        while not spi.try_lock():
            pass
        spi.configure(baudrate=6_666_000) # Configure SPI for 80MHz
        spi.unlock()

        # Initialize OLED display

        display_bus = displayio.FourWire(
            spi, chip_select=self.oled_cs, command=self.oled_dc, reset=self.oled_res
        )
        
        super(SSD1331Display, self).__init__(display_bus, width=self.screen_width, height=self.screen_height, *args, **kwargs)
   


        

