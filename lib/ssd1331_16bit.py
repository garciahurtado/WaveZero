# SSD1331.py MicroPython driver for Adafruit 0.96" OLED display
# https://www.adafruit.com/product/684

# Copyright (c) Peter Hinch 2019-2020
# Released under the MIT license see LICENSE

# Show command
# 0x15, 0, 0x5f, 0x75, 0, 0x3f  Col 0-95 row 0-63

# Initialisation command
# 0xae        display off (sleep mode)
# 0xa0, 0x72  16 bit RGB, horizontal RAM increment
# 0xa1, 0x00  Startline row 0
# 0xa2, 0x00  Vertical offset 0
# 0xa4        Normal display
# 0xa8, 0x3f  Set multiplex ratio
# 0xad, 0x8e  Ext supply
# 0xb0, 0x0b  Disable power save mode
# 0xb1, 0x31  Phase period
# 0xb3, 0xf0  Oscillator frequency
# 0x8a, 0x64, 0x8b, 0x78, 0x8c, 0x64, # Precharge
# 0xbb, 0x3a  Precharge voltge
# 0xbe, 0x3e  COM deselect level
# 0x87, 0x06  master current attenuation factor 
# 0x81, 0x91  contrast for all color "A" segment
# 0x82, 0x50  contrast for all color "B" segment 
# 0x83, 0x7d  contrast for all color "C" segment 
# 0xaf        Display on

import framebuf
import utime
import gc

from micropython import const

# https://github.com/peterhinch/micropython-nano-gui/issues/2
# The ESP32 does not work reliably in SPI mode 1,1. Waveforms look correct.
# Mode 0, 0 works on ESP and STM

# Data sheet SPI spec: 150ns min clock period 6.66MHz

CMD_DRAWLINE = b'\x21'
CMD_RECT = b'\x22'
CMD_FILL = b'\x26'
CMD_CLOCK_DIVIDE = b'\xB3'
DC_MODE_CMD = 0x00
DC_MODE_DATA = 0x01
INIT_BYTES =   b'\xAE\xA0\x76\xA1\x00\xA2\x00\xA4\xA8\x3F\xAD\x8E\xB0'\
               b'\x0B\xB1\x31\xB3\xF0\x8A\x64\x8B\x78\x8C\x64\xBB\x3A\xBE\x3E\x87'\
               b'\x06\x81\x91\x82\x50\x83\x7D\xAF'\

DELAY_FILL: int = 1000
DELAY_LINE: int = 400

HEIGHT: int = const(64)
WIDTH: int = const(96)

class SSD1331(framebuf.FrameBuffer):
    height: int
    width: int
    buffer: None

    # Convert r, g, b in range 0-255 to a 16 bit colour value RGB565
    #  acceptable to hardware: rrrrrggggggbbbbb
    # LS byte of 16 bit result is shifted out 1st
    @staticmethod
    def rgb(r, g, b):
        return ((b & 0xf8) << 5) | ((g & 0x1c) << 11) | (r & 0xf8) | ((g & 0xe0) >> 5)

    def __init__(self, spi, pincs, pindc, pinrs, height=HEIGHT, width=WIDTH):
        self._spi = spi
        self._pincs = pincs
        self._pindc = pindc  # 1 = data 0 = cmd
        self.dc_mode = DC_MODE_CMD
        self.height = height  # Required by Writer class
        self.width = width
        mode = framebuf.RGB565

        gc.collect()
        self.buffer = bytearray(self.height * self.width * 2)  # RGB565 is 2 bytes
        print(f"Buffer size: {len(self.buffer)} bytes")

        super().__init__(self.buffer, self.width, self.height, mode)
        pinrs(0)  # Pulse the reset line
        utime.sleep_ms(1)
        pinrs(1)
        utime.sleep_ms(1)

        self._write(INIT_BYTES, DC_MODE_CMD)

    def _write(self, buf, dc):
        self._pincs(1)
        self._pindc(dc)
        self._pincs(0)
        self._spi.write(buf)
        self._pincs(1)

    def _start_data(self):
        if self.dc_mode != DC_MODE_DATA:
            self._pindc(DC_MODE_DATA)
            self.dc_mode = DC_MODE_DATA

    def _start_cmd(self):
        if self.dc_mode != DC_MODE_CMD:
            self._pindc(DC_MODE_CMD)
            self.dc_mode = DC_MODE_CMD

    def set_clock_divide(self, mul):
        self._write(CMD_CLOCK_DIVIDE, DC_MODE_CMD)
        self._write(self._to_bytes(int(mul < 5), 1), DC_MODE_CMD)



    def linev2(self, x_a, y_a, x_b, y_b, color):
        r, g, b = color[0], color[1], color[2]

        #self._write_start()
        self._write_line(int(x_a), int(y_a), int(x_b), int(y_b))
        self._write_color(r, g, b)
        #self._write_end()

    def _write_line(self, x_a: int, y_a: int, x_b: int, y_b: int):
        # self._write_cmd(CMD_DRAWLINE)
        self._write(CMD_DRAWLINE, DC_MODE_CMD)

        self._write(self._to_bytes(x_a), DC_MODE_CMD)
        self._write(self._to_bytes(y_a), DC_MODE_CMD)
        self._write(self._to_bytes(x_b), DC_MODE_CMD)
        self._write(self._to_bytes(y_b), DC_MODE_CMD)

        # writeCommand((uint8_t)((color >> 11) << 1));
        # writeCommand((uint8_t)((color >> 5) & 0x3F));
        # writeCommand((uint8_t)((color << 1) & 0x3F));
        # endWrite();
        # delayMicroseconds(SSD1331_DELAYS_HWLINE);

    def _write_rect(self, x_a: int, y_a: int, x_b: int, y_b: int):
        self._write(CMD_RECT, DC_MODE_CMD)
        coords = [int(x_a),int(y_a),int(x_b),int(y_b)]
        #
        # color = [0xFF,0xFF,0xFF]
        # self._write((bytearray(coords)), DC_MODE_CMD)
        # self._write((bytearray(color)), DC_MODE_CMD)
        # self._write((bytearray(color)), DC_MODE_CMD)
        # self._write_data(self._to_bytes(bytearray(coords)))
        # self._write_data(self._to_bytes(y_a))
        # self._write_data(self._to_bytes(x_b))
        # self._write_data(self._to_bytes(y_b))
        # self._write_data(bytearray(coords))
        self._write_data(self._to_bytes([coords[0], coords[1]], 2))
        self._write_data(self._to_bytes([coords[2], coords[3]], 2))
        # self._write_data(self._to_bytes(coords[1]))
        # self._write_data(self._to_bytes(coords[2]))
        # self._write_data(self._to_bytes(0))
        #
        self._write(self._to_bytes(255), DC_MODE_CMD)
        self._write(self._to_bytes(255), DC_MODE_CMD)
        self._write(self._to_bytes(255), DC_MODE_CMD)

        self._write(self._to_bytes(255), DC_MODE_CMD)
        self._write(self._to_bytes(255), DC_MODE_CMD)
        self._write(self._to_bytes(255), DC_MODE_CMD)


        # self._write_data(bytearray([255,255,255]))
        # self._write_data(bytearray([255,255,255]))
        # self._write(self._to_bytes(coords[1]), DC_MODE_CMD)
        # self._write(self._to_bytes(coords[2]), DC_MODE_CMD)
        # self._write(self._to_bytes(coords[3]), DC_MODE_CMD)
        #self._write_end()

    def _write_color(self, r, g, b):
        self._write_data(self._to_bytes(r))
        self._write_data(self._to_bytes(g))
        self._write_data(self._to_bytes(b))

    def _write_color_bytes(self, my_bytes):
        self._write_data(self._to_bytes(my_bytes, 3))

    def _write_start(self):
        self._start_cmd()

    def _write_end(self):
        self._pincs(1)

    def _write_cmd(self, cmd):
        self._start_cmd()
        cmd = self._to_bytes(cmd)
        self._spi.write(cmd)

    def _write_data(self, data):
        self._start_data()
        self._spi.write(data)

    def _to_bytes(self, data, size: int=2):
        if isinstance(data, list):
            data = bytearray(data)
        elif isinstance(data, bytes):
            pass
        else:
            data = data.to_bytes(size, 'big')

        return data

    def show(self, _cmd=b'\x15\x00\x5f\x75\x00\x3f'):  # Pre-allocate
        self._write(_cmd, 0)
        self._write(self.buffer, 1)

    def set_offset_x(self, _cmd=b''):
        self._write(_cmd, 0)
        self._write(self.buffer, 1)

    def enable_fill(self):
        self._write(CMD_FILL, DC_MODE_CMD)
        self._write(self._to_bytes(0x01), DC_MODE_CMD)

    def disable_fill(self):
        self._write(CMD_FILL, DC_MODE_CMD)
        self._write(self._to_bytes(0x00), DC_MODE_CMD)

