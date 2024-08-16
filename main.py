import gc

from utime import sleep

from screen_app import ScreenApp

# from game_screen import GameScreen
from sprite_mgr_test_screen import SpriteMgrTestScreen
# from test_screen import TestScreen
import micropython
import time
import machine
import test_midi as midi

def main():
    machine.freq(250_000_000)
    time.sleep(2)
    current_freq = machine.freq()
    print(f"CPU: {current_freq / 1_000_000} MHz")

    check_mem()
    print("Compiler opt level: " + str(micropython.opt_level()))

    app = ScreenApp(96, 64)
    # app.load_screen(GameScreen(app.display))
    app.load_screen(SpriteMgrTestScreen(app.display))
    # app.load_screen(TitleScreen(app.display))
    # app.load_screen(TestScreen(app.display))

    print("After loading screen class")
    app.run()

def check_mem():
    gc.collect()
    print(micropython.mem_info())

if __name__ == "__main__":
    time.sleep(1)
    print("======== APP START ========")
    print(micropython.mem_info())
    midi.run()
