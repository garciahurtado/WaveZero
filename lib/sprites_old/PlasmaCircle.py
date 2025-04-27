from sprites.sprite import Sprite
import framebuf
from colors import color_util as colors
from sprites.sprite_3d import Sprite3D


class PlasmaCircle(Sprite3D):

    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            filename=None,
            frame_width=20,
            frame_height=20,
            **kwargs)

        self.pos_type = Sprite.POS_TYPE_FAR
        self.color1 = colors.rgb_to_565(colors.hex_to_rgb(0x000000))
        self.color2 = colors.rgb_to_565(colors.hex_to_rgb(0x0099FF))
        self.num_frames = 10 # Represents the max width / height, to help with scaling

    def show(self, display: framebuf.FrameBuffer):
        """Rather than blit an image onto the display, this sprite draws its own lines/rects"""
        if not self.visible:
            return False

        width = self.current_frame + 1
        height = int(width/2)
        shift = int(width/2)
        draw_x = self.draw_x + shift
        draw_y = self.draw_y - shift

        display.fill_rect(draw_x, draw_y, width, height, self.color1)
        display.rect(draw_x, draw_y, width, height, self.color2)

    def reset(self):
        """ initial conditions of the sprite before appearing on screen"""
        super().reset()
        self.has_alpha = False
        self.speed = -0.1

    def set_frame(self, frame_num):
        self.current_frame = frame_num


