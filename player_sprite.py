from sprite import Spritesheet


class PlayerSprite(Spritesheet):
    target_lane = 2
    current_lane = 2

    def __init__(self):
        super().__init__("/img/bike_sprite.bmp", 37, 22)
        self.set_alpha(0)
        self.set_frame(8)  # middle frame
        self.x = 25
        self.y = 42

    def move_left(self):
        if self.current_lane == 0:
            return

        if self.current_lane == self.target_lane:
            self.target_lane = self.current_lane - 1
        else:
            if  self.target_lane > 0:
                self.target_lane -= 1

    def move_right(self):
        if self.current_lane == 4:
            return

        if self.current_lane == self.target_lane:
            self.target_lane = self.current_lane + 1
        else:
            if self.target_lane < 4:
                self.target_lane += 1

    def turn(self, angle):
        new_frame = round(((angle * 16) + 17) / 2)
        if self.current_frame != new_frame:
            self.set_frame(new_frame)

        line_offset = angle
        return line_offset
