import _thread
import gc
import sys
from utime import sleep

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

# from screens.title_screen import TitleScreen

print(f" = EXEC ON CORE {_thread.get_ident()} (main)")

def main():
    micropython.opt_level(3)

    # max_freq = 280_000_000 # Works for rp2040
    # max_freq = 150_000_000
    # max_freq = 133_000_000
    # max_freq = 125_000_000

    # machine.freq(max_freq)
    # machine.freq(120_000_000)
    # machine.freq(80_000_000)
    # machine.freq(40_000_000)

    current_freq = machine.freq()
    print(f"CPU clock: {current_freq / 1_000_000:.2f} MHz")

    # check_mem()
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
