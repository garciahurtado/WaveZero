from game_screen import GameScreen
from screen_app import ScreenApp
from title_screen import TitleScreen


def main():
    app = ScreenApp(96, 64)
    #app.load_screen(TitleScreen())
    app.load_screen(GameScreen())
    app.run()


if __name__ == "__main__":
    main()