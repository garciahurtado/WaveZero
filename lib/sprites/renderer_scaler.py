from colors.framebuffer_palette import FramebufferPalette
from scaler.const import DEBUG
from scaler.sprite_scaler import SpriteScaler
from sprites.sprite_types import SpriteType as types, FLAG_VISIBLE, FLAG_BLINK_FLIP, FLAG_BLINK
from framebuf import FrameBuffer

class RendererScaler:
    """ A composable sprite renderer that can be used by a sprite manager (or standalone)
    to render sprites in different ways. """
    def __init__(self, display):
        self.display = display
        self.scaler = SpriteScaler(display)

    def render_sprite(self, inst, meta, images, palette):
        if not types.get_flag(inst, FLAG_VISIBLE):
            if DEBUG:
                print(">>> SPRITE IS INVISIBLE!!!")
            return False

        if types.get_flag(inst, FLAG_BLINK):
            blink_flip = types.get_flag(inst, FLAG_BLINK_FLIP)
            types.set_flag(inst, FLAG_BLINK_FLIP, blink_flip * -1)

        if hasattr(meta, 'alpha_color'):
            alpha = meta.alpha_color
        else:
            alpha = 0x0

        image = images[0]

        """ Drawing a single image or a row of them? repeats 0 and 1 mean the same thing (one image) """

        if meta.repeats < 2:
            self.scaler.draw_sprite(meta, inst, image, h_scale=inst.scale, v_scale=inst.scale)

            # self.do_blit(x=start_x, y=start_y, display=self.display, frame=image.pixels,
            #              palette=palette, alpha=alpha)
        else:
            """Also draw horizontal clones of this sprite, if needed """
            for i in range(0, meta.repeats):
                x = start_x + (meta.repeat_spacing * inst.scale * i)
                self.scaler.draw_sprite(meta, inst, image, h_scale=inst.scale, v_scale=inst.scale)

            #     self.do_blit(x=round(x), y=start_y, display=self.display, frame=image.pixels, palette=palette, alpha=alpha)
            pass

