import gc

from game_screen import GameScreen
from screen_app import ScreenApp
# from test_screen import TestScreen
# from title_screen import TitleScreen
import micropython
import time

def main():
    time.sleep(0.5)
    app = ScreenApp(96, 64)
    screen = GameScreen(app.display)

    # app.load_screen(TitleScreen(app.display))
    app.load_screen(screen)
    #app.load_screen(TestScreen(app.display))
    app.run()


if __name__ == "__main__":
    print("======== APP START ========")

    gc.collect()
    print(micropython.mem_info())
    main()