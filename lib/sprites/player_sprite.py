import asyncio
from sprites.spritesheet import Spritesheet

class PlayerSprite(Spritesheet):
    target_lane = 2
    current_lane = 2
    bike_angle = 0

    def __init__(self, camera=None, *args, **kwargs):
        super().__init__(
            filename="/img/bike_sprite.bmp",
            frame_width=32,
            frame_height=22
            )
        self.x = 32
        self.y = 42
        self.set_alpha(0)
        self.set_frame(8)  # middle frame
        self.has_physics = True
        self.moving = False
        self.bike_angle = 0
        self.turn_incr = 2.5  # lane switching speed
        self.camera = camera
        self.half_width = int(self.camera.half_width)

    def move_left(self):
        if (self.current_lane == 0):
            return

        if self.moving:
            return

        self.moving = True
        self.target_lane = self.current_lane - 1
        if self.target_lane < 0:
            self.target_lane = 0

    def move_right(self):
        if (self.current_lane == 4):
            return

        if self.moving:
            return

        self.moving = True
        self.target_lane = self.current_lane + 1

        if self.target_lane > 4:
            self.target_lane = 4

    def pick_frame(self, angle):
        new_frame = round(((angle * 16) + 17) / 2)
        if self.current_frame != new_frame:
            self.set_frame(new_frame)

        line_offset = angle
        return line_offset

    def update(self, elapsed):
        if self.target_lane == self.current_lane:
            return False

        # Handle bike switching lanes (moving left / right)
        target_lane = self.target_lane
        current_lane = self.current_lane

        target_angle = (target_lane / 2) - 1
        bike_angle = self.bike_angle
        turn_incr = self.turn_incr * (elapsed / 1000)

        if target_lane < current_lane:
            bike_angle = bike_angle - turn_incr
            if bike_angle <= target_angle:
                current_lane = target_lane
                bike_angle = target_angle
                self.moving = False

        elif target_lane > current_lane:
            bike_angle = bike_angle + turn_incr
            if bike_angle >= target_angle:
                current_lane = target_lane
                bike_angle = target_angle
                self.moving = False

        bike_angle = min(bike_angle, 1)  # Clamp the input between -1 and 1
        line_offset = self.pick_frame(bike_angle)  # bike_angle->(-1,1)

        self.x = int((line_offset * 34) + self.half_width - 16)
        self.current_lane = current_lane
        self.bike_angle = bike_angle

    def start_blink(self):
        self.blink = True
        self.has_physics = False

    async def stop_blink(self):
        await asyncio.sleep(3)
        self.blink = False
        self.visible = True
        self.active = True
        self.has_physics = True

