import gc
from screen_app import ScreenApp

from game_screen import GameScreen
from grid_test_screen import GridTestScreen
# from title_screen import TitleScreen
import micropython
import time
import driver_test

from ssd_1331 import SSD1331

def main():

    app = ScreenApp(96, 64)
    app.load_screen(GameScreen(app.display))
    # app.load_screen(GridTestScreen(app.display))
    # app.load_screen(TitleScreen(app.display))
    # app.load_screen(TestScreen(app.display))

    print("After loading screen class")
    app.run()



if __name__ == "__main__":
    time.sleep(2)
    print("======== APP START ========")

    gc.collect()
    print(micropython.mem_info())
    main()
    # driver_test.test_ssd1331_driver()