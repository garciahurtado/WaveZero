import math

import framebuf
from typing import Tuple, Optional

import framebuf as fb


class FontRenderer():
    def __init__(self, device: framebuf.FrameBuffer, font, screen_width: int, screen_height: int):
        self.device = device
        self.font = font
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.state = DisplayState()
        self.row_clip = False
        self.col_clip = False
        self.wrap = False
        self.visible = True
        # Preallocate character framebuffer so we dont end up creating tons of ephemeral objects while rendering
        self.char_framebuf = framebuf.FrameBuffer(bytearray(4), 8, 8, framebuf.MONO_HLSB)

    @staticmethod
    def set_textpos(device: framebuf.FrameBuffer, row: Optional[int] = None, col: Optional[int] = None) -> Tuple[
        int, int]:
        state = getattr(device, '_display_state', DisplayState())
        if row is not None:
            if 0 <= row < device.height:
                text_y = row
            else:
                raise ValueError('row is out of range')
        if col is not None:
            if 0 <= col < device.width:
                text_x = col
            else:
                raise ValueError('col is out of range')
        device._display_state = state
        return text_y, text_x

    def set_clip(self, row_clip: bool, col_clip: bool, wrap: bool) -> Tuple[bool, bool, bool]:
        self.row_clip = row_clip
        self.col_clip = col_clip
        self.wrap = wrap
        return self.row_clip, self.col_clip, self.wrap

    def render_text(self, text: str, invert: bool = False) -> None:
        pass

    def render_char(self, char: str, invert: bool = False) -> None:
        pass

    def get_char_width(self, char: str) -> int:
        glyph, _, width = self.font.get_ch(char)
        # Calculate actual width by finding the rightmost non-zero column
        for col in range(width - 1, -1, -1):
            for row in range(self.font.height()):
                if glyph[row * ((width + 7) // 8) + col // 8] & (1 << (7 - col % 8)):
                    return col + 1
        return 0

    def stringlen(self, string: str) -> int:
        return sum(self.get_char_width(char) for char in string)


class MonochromeWriter(FontRenderer):
    def __init__(self, device: framebuf.FrameBuffer, font, screen_width: int, screen_height: int):
        super().__init__(device, font, screen_width, screen_height)
        self.orig_x = 0
        self.orig_y = 0
        self.text_x = 0
        self.text_y = 0


    def render_char(self, char: str, invert: bool = False) -> None:
        print(f"CHAR IS '{char}'")
        glyph, height, width = self.font.get_ch(char)
        if self.text_y + height > self.screen_height:
            if self.row_clip:
                return
            self._newline()
        if self.text_x + width > self.screen_width:
            if self.col_clip:
                return
            if self.wrap:
                self._newline()
            else:
                return

        buf = bytearray(glyph)
        if invert:
            buf = bytearray(b ^ 0xFF for b in buf)
        fb = framebuf.FrameBuffer(buf, width, height, framebuf.MONO_HLSB)
        self.device.blit(fb, self.text_x, self.text_y, -1)
        self.text_x += width

    def _newline(self) -> None:
        self.text_y += self.font.height()
        self.text_x = 0
        if self.text_y + self.font.height() > self.screen_height:
            if not self.row_clip:
                self.device.scroll(0, -self.font.height())
                self.text_y -= self.font.height()

    def tabsize(self, size: Optional[int] = None) -> int:
        if size is not None:
            self._tabsize = max(1, size)
        return self._tabsize

    def show(self, canvas):
        if not self.visible:
            return False

        x, y = self.orig_x, self.orig_y
        # print(f"BLIT AT {x}, {y}")
        canvas.blit(self.pixels, x, y, -1, self.palette)


class ColorWriter():
    def __init__(self, device: framebuf.FrameBuffer, font,
                 text_width: int, text_height: int, palette, fixed_width: int = None, color_format: int = fb.GS4_HMSB):

        self.device = device
        self.font = font
        self.text_height = text_height
        self.text_width = text_width
        self.orig_x = 0
        self.orig_y = 0
        self.text_x = 0
        self.text_y = 0
        self.visible = True
        self.palette = palette
        self.fixed_width = fixed_width
        self.dirty = False

        # print(f"WRITER WITH COLORS: x{palette[0]:#06x} and x{palette[1]:#06x}")
        if color_format:
            self.color_format = color_format
        else:
            if font.hmap():
                self.color_format = framebuf.MONO_HMSB if font.reverse() else framebuf.MONO_HLSB
            else:
                raise ValueError('Font must be horizontally mapped.')

        # Create a GS4_HMSB framebuffer for the text
        if color_format in (fb.MONO_HLSB, fb.MONO_HMSB):
            pixels_per_byte = 8
        elif color_format == fb.GS4_HMSB:
            pixels_per_byte = 2
        elif color_format == fb.GS8:
            pixels_per_byte = 1
        else:
            pixels_per_byte = 1 / 2

        buffer_size = math.ceil((text_width * text_height) / pixels_per_byte)
        self.pixels = framebuf.FrameBuffer(bytearray(buffer_size),
                                           text_width, text_height, self.color_format)

    def render_text(self, text: str, invert: bool = False) -> None:
        self.text_x = self.orig_x
        self.text_y = self.orig_y

        # Use a memoryview to avoid creating new objects for each character
        text_view = memoryview(text.encode('ascii'))

        for char_byte in text_view:
            # Pass the byte directly to render_char
            self.render_char(char_byte, invert)

        self.text_x = self.orig_x
        self.text_y = self.orig_y

    def render_char(self, char: str, invert: bool = False) -> None:
        if isinstance(char, str):
            char_idx = ord(char)
        elif isinstance(char, int):
            char_idx = char
        else:
            raise TypeError("char must be a string or integer")

        glyph, height, width = self.font.get_ch(char_idx)
        if self.fixed_width:
            width = self.fixed_width

        # print(f"RENDER {char}(w:{width}) at {self.text_x},{self.text_y} (on {self.text_width}x{self.text_height}) -GLYPH: {glyph}")
        # for line in glyph:
        #     print(f"{line:>011b}")

        if self.text_x + width > self.text_width:
            self.newline()
            pass
        if self.text_y + height > self.text_height:
            pass
            # return  # No space left in the buffer

        self.char_framebuf = framebuf.FrameBuffer(bytearray(glyph), width, height, framebuf.MONO_HLSB)

        self.pixels.blit(self.char_framebuf, self.text_x, 0, -1, self.palette)
        self.text_x += width

    def newline(self) -> None:
        self.text_y += self.font.height()
        self.text_x = 0
        if self.text_y + self.font.height() > self.text_height:
            # Scroll the buffer
            self.pixels.scroll(0, -self.font.height())
            self.text_y -= self.font.height()
            # Clear the new line
            # self.pixels.fill_rect(0, self.text_y, self.text_width, self.font.height(), 1)


    def show(self, display, palette=None):
        if not self.visible:
            return False

        if not palette:
            palette = self.palette

        if self.color_format in (fb.MONO_HMSB, fb.GS4_HMSB, fb.GS8):
            """ Only indexed formats need a palette"""
            display.blit(self.pixels, self.orig_x, self.orig_y, -1, palette)
        else:
            display.blit(self.pixels, self.orig_x, self.orig_y, -1, palette)

    def set_clip(self, row_clip: bool, col_clip: bool, wrap: bool) -> Tuple[bool, bool, bool]:
        self.row_clip = row_clip
        self.col_clip = col_clip
        self.wrap = wrap
        return self.row_clip, self.col_clip, self.wrap

    def get_char_width(self, char: str) -> int:
        glyph, _, width = self.font.get_ch(char)
        # Calculate actual width by finding the rightmost non-zero column
        for col in range(width - 1, -1, -1):
            for row in range(self.font.height()):
                if glyph[row * ((width + 7) // 8) + col // 8] & (1 << (7 - col % 8)):
                    return col + 1
        return 0

    def stringlen(self, string: str) -> int:
        return sum(self.get_char_width(char) for char in string)

    def color_size(self, byte_size, color_mode):
        """ How many colors fit in the given byte_size at the current color format"""

        if color_mode == fb.RGB565:
            num_colors = byte_size // 2
        elif color_mode == fb.GS8:
            num_colors = byte_size
        elif color_mode == fb.GS4_HMSB:
            num_colors = byte_size * 2
        else:
            num_colors = byte_size * 4

        return num_colors

    def byte_size(self, num_colors, color_mode):
        """ Return the size, in bytes, of the number of colors specified at the current color format"""

        if color_mode == fb.RGB565:
            size = num_colors * 2
        elif color_mode == fb.GS8:
            size = num_colors
        elif color_mode == fb.GS4_HMSB:
            size = num_colors // 2
        else:
            size = num_colors // 4

        return size
