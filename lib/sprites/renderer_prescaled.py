from colors.framebuffer_palette import FramebufferPalette
from scaler.const import DEBUG
from sprites.sprite_types import SpriteType as types, FLAG_VISIBLE, FLAG_BLINK_FLIP, FLAG_BLINK
from framebuf import FrameBuffer

class RendererPrescaled:
    """ A composable sprite renderer that can be used by a sprite manager (or standalone)
    to render sprites in different ways. """

    def __init__(self, display):
        self.display = display

    def render_sprite(self, sprite, meta, images, palette):
        if hasattr(meta, 'alpha_color'):
            alpha = meta.alpha_color
        else:
            alpha = 0x0

        # if meta.rotate_palette:
        #     color = meta.rotate_palette[sprite.color_rot_idx]
        #     # Apply the rotated color to the sprite's palette
        #     palette.set_int(0, color)

        frame_id = sprite.current_frame  # 255 sometimes ???
        image = images[frame_id]

        start_x = sprite.draw_x
        start_y = sprite.draw_y

        """ Drawing a single image or a row of them? repeats 0 and 1 mean the same thing (one image) """

        if meta.repeats < 2:
            self.do_blit(x=start_x, y=start_y, display=self.display, frame=image.pixels,
                         palette=palette, alpha=alpha)
        else:
            """Also draw horizontal clones of this sprite, if needed """
            for i in range(0, meta.repeats):
                x = start_x + (meta.repeat_spacing * sprite.scale * i)
                self.do_blit(x=round(x), y=start_y, display=self.display, frame=image.pixels, palette=palette, alpha=alpha)

    # @timed
    def do_blit(self, x: int, y: int, display: FrameBuffer, frame, palette, alpha=None):
        if alpha is not None:
            display.blit(frame, x, y, alpha, palette)
        else:
            display.blit(frame, x, y, -1, palette)

        return True
