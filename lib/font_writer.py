# writer.py Implements the Writer class.
# Handles colour, word wrap and tab stops

# V0.5.1 Dec 2022 Support 4-bit color display drivers.
# V0.5.0 Sep 2021 Color now requires firmware >= 1.17.
# V0.4.3 Aug 2021 Support for fast blit to color displays (PR7682).
# V0.4.0 Jan 2021 Improved handling of word wrap and line clip. Upside-down
# rendering no longer supported: delegate to device driver.
# V0.3.5 Sept 2020 Fast rendering option for color displays

# Released under the MIT License (MIT). See LICENSE.
# Copyright (c) 2019-2021 Peter Hinch

# A Writer supports rendering text to a Display instance in a given font.
# Multiple Writer instances may be created, each rendering a font to the
# same Display object.

# Timings were run on a pyboard D SF6W comparing slow and fast rendering
# and averaging over multiple characters. Proportional fonts were used.
# 20 pixel high font, timings were 5.44ms/467μs, gain 11.7 (freesans20).
# 10 pixel high font, timings were 1.76ms/396μs, gain 4.36 (arial10).


import framebuf
from uctypes import bytearray_at, addressof
from sys import implementation
import color_util as colors
from framebuffer_palette import FramebufferPalette

__version__ = (0, 5, 1)

fast_mode = True  # Does nothing. Kept to avoid breaking code.

class DisplayState():
    text_row: int = 0
    text_col: int = 0

    def __init__(self):
        self.text_row = 0
        self.text_col = 0

def _get_id(device):
    # if not isinstance(device, framebuf.FrameBuffer):
    #     raise ValueError('Device must be derived from FrameBuffer.')
    return id(device)

# Basic Writer class for monochrome displays
class Writer():

    state = {}  # Holds a display state for each device
    text_height: int
    text_width: int
    visible = True
    screen_width: int
    screen_height: int

    @staticmethod
    def set_textpos(device, row=None, col=None, ):
        devid = _get_id(device)

        if devid not in Writer.state:
            Writer.state[devid] = DisplayState()
        s = Writer.state[devid]  # Current state
        if row is not None:
            if row < 0 or row >= Writer.screen_height:
                raise ValueError('row is out of range')
            s.text_row = row
        if col is not None:
            if col < 0 or col >= Writer.screen_width:
                raise ValueError('col is out of range')
            s.text_col = col
        return s.text_row,  s.text_col

    def __init__(self, device, font, text_width, text_height, screen_width=None, screen_height=None, verbose=True):
        self.text_height = text_height
        self.text_width = text_width

        Writer.screen_width = screen_width
        Writer.screen_height = screen_height

        self.devid = _get_id(device)
        self.device = device
        if self.devid not in Writer.state:
            Writer.state[self.devid] = DisplayState()
        self.font = font
        if font.height() >= screen_height or font.max_width() >= screen_width:
            raise ValueError('Font too large for screen')
        # Allow to work with reverse or normal font mapping
        if font.hmap():
            self.map = framebuf.MONO_HMSB if font.reverse() else framebuf.MONO_HLSB
        else:
            raise ValueError('Font must be horizontally mapped.')
        if verbose:
            fstr = 'Orientation: Horizontal. Reversal: {}. Width: {}. Height: {}.'
            #print(fstr.format(font.reverse(), device.width, device.height))
            #print('Start row = {} col = {}'.format(self._getstate().text_row, self._getstate().text_col))
        self.screenwidth = screen_width  # In pixels
        self.screenheight = screen_height
        self.bgcolor = 0  # Monochrome background and foreground colors
        self.fgcolor = 1
        self.row_clip = False  # Clip or scroll when screen full
        self.col_clip = False  # Clip or new line when row is full
        self.wrap = False  # Word wrap
        self.cpos = 0
        self.tab = 4

        self.glyph = None  # Current char
        self.char_height = 0
        self.char_width = 0
        self.clip_width = 0

    def _getstate(self):
        return Writer.state[self.devid]

    def _newline(self):
        s = self._getstate()
        height = self.font.height()
        s.text_row += height
        s.text_col = 0
        margin = self.screenheight - (s.text_row + height)
        y = self.screenheight + margin
        if margin < 0:
            if not self.row_clip:
                self.device.scroll(0, margin)
                self.device.fill_rect(0, y, self.screenwidth, abs(margin), self.bgcolor)
                s.text_row += margin

    def set_clip(self, row_clip=None, col_clip=None, wrap=None):
        if row_clip is not None:
            self.row_clip = row_clip
        if col_clip is not None:
            self.col_clip = col_clip
        if wrap is not None:
            self.wrap = wrap
        return self.row_clip, self.col_clip, self.wrap

    @property
    def height(self):  # Property for consistency with device
        return self.font.height()

    def _printstring(self, string, invert=False):
        print("In WRITER printstring")

        # word wrapping. Assumes words separated by single space.
        lines = string.split('\n')
        last = len(lines) - 1
        for n, s in enumerate(lines):
            if s:
                self.render_text(s, invert)
            if n != last:
                self.render_char('\n')

    def _render_text(self, text, is_inverted):
        """
        Render a line of text, wrapping if enabled and necessary.

        :param text: The text to render
        :param is_inverted: Whether to invert the text colors
        """
        print(f"Rendering text: {text}")

        remaining_text = None
        if self.wrap and self.is_text_wider_than_screen(text):
            wrap_position = self.find_wrap_position(text)
            if wrap_position > 0:
                remaining_text = text[wrap_position + 1:]
                text = text[:wrap_position].rstrip()

        for character in text:
            self.render_char(character, is_inverted)

        if remaining_text:
            self.render_char('\n')
            self.render_text(remaining_text, is_inverted)  # Recursive call for remaining text

    def is_text_wider_than_screen(self, text, check_overflow=False):
        """
        Calculate if the text width exceeds the screen width.

        :param text: The text to measure
        :param check_overflow: If True, return as soon as width exceeds screen
        :return: Boolean if check_overflow, else pixel width of text
        """
        if not text:
            return 0

        start_column = self._getstate().text_col
        screen_width = self.screenwidth
        total_width = 0

        for character in text:
            _, _, char_width = self.font.get_ch(character)
            total_width += char_width
            if check_overflow and total_width + start_column > screen_width:
                return True

        # Adjust width calculation for the last character if necessary
        if check_overflow and total_width + start_column > screen_width:
            total_width += self.get_char_width(text[-1]) - char_width

        return total_width + start_column > screen_width if check_overflow else total_width

    def find_wrap_position(self, text):
        """
        Find the position to wrap the text to fit the screen width.

        :param text: The text to wrap
        :return: The position to wrap the text
        """
        wrap_text = text[:]
        while self.is_text_wider_than_screen(wrap_text, True):
            wrap_position = wrap_text.rfind(' ')
            wrap_text = wrap_text[:wrap_position].rstrip()
        return wrap_position if wrap_position > 0 else 0

    def stringlen(self, string, oh=False):
        if not string:
            return 0
        sc = self._getstate().text_col  # Start column
        wd = self.screenwidth
        l = 0

        for char in string:
            _, _, char_width = self.font.get_ch(char)
            l += char_width
            if oh and l + sc > wd:
                return True  # All done. Save time.

        # Handle last character specially if needed
        if string and oh and l + sc > wd:
            l += self.get_char_width(string[-1]) - char_width

        return l + sc > wd if oh else l

    # Return the printable width of a glyph less any blank columns on RHS
    def get_char_width(self, char):
        """
        Get the true width of a character, accounting for trailing spaces.

        :param char: The character to measure
        :return: The true width of the character
        """

        glyph, ht, wd = self.font.get_ch(char)
        div, mod = divmod(wd, 8)
        gbytes = div + 1 if mod else div  # No. of bytes per row of glyph
        mc = 0  # Max non-blank column
        data = glyph[(wd - 1) // 8]  # Last byte of row 0
        for row in range(ht):  # Glyph row
            for col in range(wd -1, -1, -1):  # Glyph column
                gbyte, gbit = divmod(col, 8)
                if gbit == 0:  # Next glyph byte
                    data = glyph[row * gbytes + gbyte]
                if col <= mc:
                    break
                if data & (1 << (7 - gbit)):  # Pixel is lit (1)
                    mc = col  # Eventually gives rightmost lit pixel
                    break
            if mc + 1 == wd:
                break  # All done: no trailing space
        # print('Truelen', char, wd, mc + 1)  # TEST
        return mc + 1

    def get_char(self, char, recurse):
        if not recurse:  # Handle tabs
            if char == '\n':
                self.cpos = 0
            elif char == '\t':
                nspaces = self.tab - (self.cpos % self.tab)
                if nspaces == 0:
                    nspaces = self.tab
                while nspaces:
                    nspaces -= 1
                    self.render_char(' ', recurse=True)
                self.glyph = None  # All done
                return

        self.glyph = None  # Assume all done
        if char == '\n':
            self._newline()
            return
        glyph, char_height, char_width = self.font.get_ch(char)
        s = self._getstate()
        np = None  # Allow restriction on printable columns
        if s.text_row + char_height > self.screenheight:
            if self.row_clip:
                return
            self._newline()
        oh = s.text_col + char_width - self.screenwidth  # Overhang (+ve)
        if oh > 0:
            if self.col_clip or self.wrap:
                np = char_width - oh  # No. of printable columns
                if np <= 0:
                    return
            else:
                self._newline()
        self.glyph = glyph
        self.char_height = char_height
        self.char_width = char_width
        self.clip_width = char_width if np is None else np

    # Method using blitting. Efficient rendering for monochrome displays.
    # Tested on SSD1306. Invert is for black-on-white rendering.
    def _render_char(self, char, invert=False, recurse=False):
        s = self._getstate()
        self.get_char(char, recurse)
        if self.glyph is None:
            return  # All done
        buf = bytearray(self.glyph)
        if invert:
            for i, v in enumerate(buf):
                buf[i] = 0xFF & ~ v
        char_pixels = framebuf.FrameBuffer(buf, self.clip_width, self.char_height, self.map)

        print(f"text in {s.text_col} / char width: {self.clip_width}")
        self.pixels.blit(char_pixels, s.text_col, s.text_row, -1, self.palette)
        s.text_col += self.char_width
        self.cpos += 1

    def tabsize(self, value=None):
        if value is not None:
            self.tab = value
        return self.tab

    def setcolor(self, *_):
        return self.fgcolor, self.bgcolor

# Writer for colour displays.
class ColorWriter(Writer):
    palette: framebuf.FrameBuffer
    pixels: framebuf.FrameBuffer
    text_x = 0
    text_y = 0

    @staticmethod
    def create_color(ssd, idx, r, g, b):
        c = ssd.rgb(r, g, b)
        if not hasattr(ssd, 'lut'):
            return c
        if not 0 <= idx <= 15:
            raise ValueError('Color nos must be 0..15')
        x = idx << 1
        ssd.lut[x] = c & 0xff
        ssd.lut[x + 1] = c >> 8
        return idx

    def __init__(self, device, font, text_width, text_height, screen_width=None, screen_height=None, verbose=True):
        self.text_height = text_height
        self.text_width = text_width

        ColorWriter.screen_width = screen_width
        ColorWriter.screen_height = screen_height

        self.devid = _get_id(device)
        self.device = device
        if self.devid not in Writer.state:
            ColorWriter.state[self.devid] = DisplayState()
        self.font = font
        if (font.height() >= screen_height or
                font.max_width() >= screen_width):
            raise ValueError('Font too large for screen')

        # Allow to work with reverse or normal font mapping
        if font.hmap():
            self.map = framebuf.MONO_HMSB if font.reverse() else framebuf.MONO_HLSB
        else:
            raise ValueError('Font must be horizontally mapped.')
        if verbose:
            fstr = 'Orientation: Horizontal. Reversal: {}. Width: {}. Height: {}.'
            # print(fstr.format(font.reverse(), device.width, device.height))
            # print('Start row = {} col = {}'.format(self._getstate().text_row, self._getstate().text_col))
        self.screenwidth = screen_width  # In pixels
        self.screenheight = screen_height
        self.bgcolor = 0  # Monochrome background and foreground colors
        self.fgcolor = 1
        self.row_clip = False  # Clip or scroll when screen full
        self.col_clip = False  # Clip or new line when row is full
        self.wrap = False  # Word wrap
        self.cpos = 0
        self.tab = 4

        self.glyph = None  # Current char
        self.char_height = 0
        self.char_width = 0
        self.clip_width = 0

        self.default_bgcolor = self.bgcolor
        self.default_fgcolor = self.fgcolor

        my_palette = FramebufferPalette(bytearray(2*2))
        self.palette = my_palette

        pixels = bytearray(self.text_width * self.text_height)
        self.pixels = framebuf.FrameBuffer(pixels, self.text_width, self.text_height, self.map)

    def set_colors(self, fgcolor, bgcolor):
        self.fgcolor = fgcolor
        self.bgcolor = bgcolor

        for i, new_color in enumerate([bgcolor, fgcolor]):
            self.palette.pixel(i, 0, colors.bytearray_to_int(colors.byte3_to_byte2(new_color)))

    def printstring(self, string, invert=False):
        print("In COLORWRITER printstring")

        # word wrapping. Assumes words separated by single space.
        lines = string.split('\n')
        last = len(lines) - 1
        for n, s in enumerate(lines):
            if s:
                self.render_text(s, invert)
            if n != last:
                self.render_char('\n')

    def render_text(self, text, is_inverted):
        """
        Render a line of text, wrapping if enabled and necessary.

        :param text: The text to render
        :param is_inverted: Whether to invert the text colors
        """
        print(f"Rendering text: {text}")

        remaining_text = None
        if self.wrap and self.is_text_wider_than_screen(text):
            wrap_position = self.find_wrap_position(text)
            if wrap_position > 0:
                remaining_text = text[wrap_position + 1:]
                text = text[:wrap_position].rstrip()

        for character in text:
            self.render_char(character, is_inverted)

        if remaining_text:
            self.render_char('\n')
            self.render_text(remaining_text, is_inverted)  # Recursive call for remaining text

    def render_char(self, char, invert=False, recurse=False):
        s = self._getstate()
        self.get_char(char, recurse)
        if self.glyph is None:
            return  # All done
        buf = bytearray_at(addressof(self.glyph), len(self.glyph))
        char_pixels = framebuf.FrameBuffer(buf, self.clip_width, self.char_height, self.map)

        self.pixels.blit(char_pixels, s.text_col, s.text_row)
        s.text_col += self.char_width
        self.cpos += 1

    def show(self, display):
        if not self.visible:
            return False

        x, y = self.text_x, self.text_y
        display.blit(self.pixels, x, y, -1, self.palette)

    def setcolor(self, fgcolor=None, bgcolor=None):
        if fgcolor is None and bgcolor is None:
            self.fgcolor = self.default_fgcolor
            self.bgcolor = self.default_bgcolor
        else:
            if fgcolor is not None:
                self.fgcolor = fgcolor
            if bgcolor is not None:
                self.bgcolor = bgcolor
        return self.fgcolor, self.bgcolor
