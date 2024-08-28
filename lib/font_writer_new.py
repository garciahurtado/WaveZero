import framebuf
from typing import Tuple, Optional

from framebuffer_palette import FramebufferPalette
import color_util as colors

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
        self.bgcolor = 0
        self.fgcolor = 1
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
        print(f"BLIT AT {x}, {y}")
        canvas.blit(self.pixels, x, y, -1, self.palette)


class ColorWriter():
    def __init__(self, device: framebuf.FrameBuffer, font,
                 text_width: int, text_height: int, palette, fixed_width: int = None):

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

        # print(f"WRITER WITH COLORS: x{palette[0]:#06x} and x{palette[1]:#06x}")
        if font.hmap():
            self.color_format = framebuf.MONO_HMSB if font.reverse() else framebuf.MONO_HLSB
        else:
            raise ValueError('Font must be horizontally mapped.')


        # print(self.palette.pixel(0,0))
        # print(self.palette.pixel(1,0))
        self.pixels = framebuf.FrameBuffer(bytearray(self.text_width * self.text_height),
                                           self.text_width, self.text_height, self.color_format)

    def render_text(self, text: str, invert: bool = False) -> None:
        self.text_x = self.orig_x
        self.text_y = self.orig_y

        # for char in text:
        #     if char == '\n':
        #         self.newline()
        #     else:
        #         self.render_char(char, invert)

        for char in text:
            self.render_char(char, invert)

        self.text_x = self.orig_x
        self.text_y = self.orig_y

    def render_char(self, char: str, invert: bool = False) -> None:
        glyph, height, width = self.font.get_ch(char)
        if self.fixed_width:
            width = self.fixed_width

        # print(f"RENDER {char}(w:{width}) at {self.text_x},{self.text_y} (on {self.text_width}x{self.text_height})")

        if self.text_x + width > self.text_width:
            self.newline()
        if self.text_y + height > self.text_height:
            return  # No space left in the buffer

        buffer = bytearray(glyph)
        fb = framebuf.FrameBuffer(buffer, width, height, self.color_format)
        self.pixels.blit(fb, self.text_x, self.text_y, -1, self.palette)
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

