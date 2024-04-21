import random
import utime

class ScanlineFade:
    def __init__(self, display):
        self.display = display
        self.filled_lines = set()
        self.height = display.height  # Store the height for later use

    def start(self):
        while len(self.filled_lines) < self.height:
            # Generate a random y coordinate with a bias towards the top and bottom
            y = random.randint(0, self.height - 1)
            if y < self.height / 2:
                y = random.randint(0, y)
            else:
                y = random.randint(y, self.height - 1)
            if y not in self.filled_lines:
                self.display.hline(0, y, self.display.width, 0)  # Fill with black
                self.filled_lines.add(y)
                self.display.show()  # Update the display
                utime.sleep_ms(7)


