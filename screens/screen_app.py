import framebuf
from display_init import get_display
# from screens.screen import Screen


class ScreenApp:
    display: framebuf.FrameBuffer
    screens = []
    screen_width: int = 0
    screen_height: int = 0

    def __init__(self, screen_width: int, screen_height: int):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.display = get_display()

    def load_screen(self, screen):
        screen.app = self
        self.screens.append(screen)

    def run(self):
        if not self.screens:
            raise AssertionError("No screens registered with app!")

        for screen in self.screens:
            screen.run()
