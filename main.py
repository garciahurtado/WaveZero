import micropython

from screens.test_screen import TestScreen

micropython.opt_level(1)
import gc

gc.threshold(15000) # in bytes

import _thread
import gc
import utime
from utime import sleep

# from mpdb.mpdb import Mpdb
# import frozen_img # Created with freezefs: https://github.com/bixb922/freezeFS
from screens.screen_app import ScreenApp
from screens.game_screen import GameScreen
from screens.game_screen_test import GameScreenTest
# from screens.title_screen import TitleScreen
# from screens.test_screen import TestScreen
# from screens.test_screen_starfield import TestScreenStarfield

import machine
micropython.alloc_emergency_exception_buf(100)

# from screens.title_screen import TitleScreen

print(f" = MAIN.PY ON THREAD #{_thread.get_ident()} (main)")

def main():
    utime.sleep_ms(50)

    # max_freq = 266_000_000 # RP2350
    # max_freq = 280_000_000 # Works for rp2040
    # max_freq = 150_000_000
    # max_freq = 133_000_000
    # max_freq = 125_000_000
    # max_freq = 96_000_000
    # max_freq = 64_000_000

    # machine.freq(max_freq)

    current_freq = machine.freq()
    print(f"CPU clock: {current_freq / 1_000_000:.2f} MHz")
    check_mem()

    print("Compiler opt level: " + str(micropython.opt_level()))
    sleep(2)

    app = ScreenApp(96, 64)

    # app.load_screen(TitleScreen(app.display))
    app.load_screen(GameScreen(app.display))
    # app.load_screen(TestScreen(app.display))
    # app.load_screen(GameScreenTest(app.display))
    # app.load_screen(TestScreenStarfield(app.display))

    app.run()


def check_mem():
    # gc.collect()
    print(micropython.mem_info())


if __name__ == "__main__":
    print("======== APP START ========")
    check_mem()

    main()
