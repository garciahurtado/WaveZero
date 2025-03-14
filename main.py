import _thread
import gc
import sys

import utime
from utime import sleep

from scaler.const import BUS_CTRL_BASE, BUS_PRIORITY, XOSC_CTRL, XOSC_BASE, XOSC_ENABLE
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
bus_ctrl = mem32[BUS_PRIORITY]
# bus_ctrl = bus_ctrl | (1 << 12)   # DMA_W
# bus_ctrl = bus_ctrl | (1 << 8)      # DMA_R
# bus_ctrl = bus_ctrl | (1 << 4)      # PROC_1
# bus_ctrl = bus_ctrl | (1 << 0)      # PROC_0
# mem32[BUS_PRIORITY] = bus_ctrl

print(f" = BUS CTRL BITS (0-12): ........ ........ ..{bus_ctrl:>013b}")
# mem32[0x40060008] = 0x01

DMA_ACC_ADDR = 0x40060000 + 0x44
current = mem32[DMA_ACC_ADDR]
# mem32[DMA_ACC_ADDR] = current # DMA ACCESS
print(f"Current: {current:08X}")

# Define clock control registers
CLOCKS_BASE = 0x40010000
CLK_REF_SELECTED = CLOCKS_BASE + 0x38
CLK_SYS_SELECTED = CLOCKS_BASE + 0x44
CLK_PERI_SELECTED = CLOCKS_BASE + 0x50

# Configure peripheral clock (used by DMA and PIO)
def configure_peri_clock(source=0, divider=1):
    # source: 0=clk_sys, 1=clk_usb, 2=clk_adc, 3=clk_rtc
    ctrl = (source << 5) | (1 << 11)  # Enable the clock with selected source
    # mem32[CLK_PERI_CTRL] = ctrl
    # If using a divider, you'd set it separately

def main():
    micropython.opt_level(0)

    # Enable XOSC clock
    old_ctrl = mem32[XOSC_BASE + XOSC_CTRL]
    new_ctrl = old_ctrl | XOSC_ENABLE
    # mem32[XOSC_BASE + XOSC_CTRL] = new_ctrl

    value1 = mem32[CLK_REF_SELECTED]
    value2 = mem32[CLK_SYS_SELECTED]
    value3 = mem32[CLK_PERI_SELECTED]

    print("CLOCK SOURCES:")
    print("---------------")
    print(f"REF_SEL:  {value1:032b}")
    print(f"SYS_SEL:  {value2:032b}")
    print(f"PERI_SEL: {value3:032b}")

    utime.sleep_ms(50)

    # max_freq = 280_000_000 # Works for rp2040
    # max_freq = 150_000_000
    # max_freq = 133_000_000
    # max_freq = 125_000_000
    # max_freq = 80_000_000
    # max_freq = 40_000_000
    # max_freq = 52_000_000

    # machine.freq(max_freq)

    current_freq = machine.freq()
    print(f"CPU clock: {current_freq / 1_000_000:.2f} MHz")
    check_mem()
    print("Compiler opt level: " + str(micropython.opt_level()))

    sleep(2)

    app = ScreenApp(96, 64)

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
