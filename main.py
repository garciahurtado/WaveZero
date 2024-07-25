import gc
from screen_app import ScreenApp

from game_screen import GameScreen
from grid_test_screen import GridTestScreen
# from title_screen import TitleScreen
# from test_screen import TestScreen
import micropython
import time
import machine

def main():
    machine.freq(250_000_000)
    time.sleep(1)
    current_freq = machine.freq()
    print(f"CPU: {current_freq / 1_000_000} MHz")

    app = ScreenApp(96, 64)
    # app.load_screen(GameScreen(app.display))
    app.load_screen(GridTestScreen(app.display))
    # app.load_screen(TitleScreen(app.display))
    # app.load_screen(TestScreen(app.display))

    print("After loading screen class")
    app.run()



if __name__ == "__main__":
    time.sleep(1)
    print("======== APP START ========")

    gc.collect()
    print(micropython.mem_info())
    main()
