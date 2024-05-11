import gc
from game_screen import GameScreen
from screen_app import ScreenApp
# from test_screen import TestScreen
# from title_screen import TitleScreen
import micropython
import time

def main():
    time.sleep(2)
    app = ScreenApp(96, 64)
    game_screen = GameScreen(app.display)
    app.load_screen(game_screen)

    print("After loading screen class")

    # app.load_screen(TitleScreen(app.display))
    # app.load_screen(TestScreen(app.display))
    app.run()


if __name__ == "__main__":
    print("======== APP START ========")

    gc.collect()
    print(micropython.mem_info())
    main()
