import _thread
import gc
import sys

import utime
from utime import sleep

from scaler.const import BUS_CTRL_BASE, BUS_PRIORITY, XOSC_CTRL, XOSC_BASE, XOSC_ENABLE, ACCESS_CTRL_DMA, \
    ACCESS_CTRL_PIO0, ACCESS_CTRL_PIO1, ACCESS_CTRL_DMA_ATOM
from screens.game_screen_test import GameScreenTest
# import frozen_img # Created with freezefs: https://github.com/bixb922/freezeFS
from screens.screen_app import ScreenApp
from screens.test_screen import TestScreen
from screens.game_screen import GameScreen
from screens.title_screen import TitleScreen
# from screens.test_screen import TestScreen
from screens.test_screen_starfield import TestScreenStarfield

import micropython
import machine
from machine import mem32

# from screens.title_screen import TitleScreen

print(f" = EXEC ON CORE {_thread.get_ident()} (main)")

# Define clock control registers

def main():
    micropython.opt_level(0)
    utime.sleep_ms(50)

    # max_freq = 280_000_000 # Works for rp2040
    # max_freq = 150_000_000
    # max_freq = 133_000_000
    # max_freq = 125_000_000
    # max_freq = 80_000_000
    # max_freq = 52_000_000
    # max_freq = 48_000_000
    # max_freq = 24_000_000

    # machine.freq(max_freq)

    current_freq = machine.freq()
    print(f"CPU clock: {current_freq / 1_000_000:.2f} MHz")
    check_mem()
    print("Compiler opt level: " + str(micropython.opt_level()))

    sleep(2)

    app = ScreenApp(96, 64)

    # mem32[ACCESS_CTRL_PIO0] = 0xFFFFFFFF # All permissions open for PIO0
    # mem32[ACCESS_CTRL_PIO1] = 0xFFFFFFFF # All permissions open for PIO1
    #
    # value0 = mem32[ACCESS_CTRL_DMA]
    # value1 = mem32[ACCESS_CTRL_PIO0]
    # value2 = mem32[ACCESS_CTRL_PIO1]

    # mem32[ACCESS_CTRL_DMA_ATOM] = 0b00000000000000000000000000000001
    # mem32[ACCESS_CTRL_PIO0] = value1 | 0x00000000 # All permissions open for DMA
    # mem32[ACCESS_CTRL_PIO1] = value2 | 0x00000000 # All permissions open for DMA
    #
    # print(f"BUS_PERMS (DMA)  {value0:>032b}")
    # print(f"BUS_PERMS (PIO0) {value1:>032b}")
    # print(f"BUS_PERMS (PIO1) {value2:>032b}")

    # app.load_screen(TitleScreen(app.display))
    app.load_screen(GameScreenTest(app.display))
    # app.load_screen(TestScreen(app.display))
    # app.load_screen(TestScreenStarfield(app.display))

    app.run()

def check_mem():
    gc.collect()
    print(micropython.mem_info())

if __name__ == "__main__":
    print("======== APP START ========")
    check_mem()

    main()
