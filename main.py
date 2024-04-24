from game_screen import GameScreen
from screen_app import ScreenApp
from title_screen import TitleScreen
import time

def main():
    time.sleep(1)
    app = ScreenApp(96, 64)
    #app.load_screen(TitleScreen(app.display))
    app.load_screen(GameScreen(app.display))
    app.run()


if __name__ == "__main__":
    main()