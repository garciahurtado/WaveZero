import math

from framebuf import FrameBuffer

from images.image_loader import ImageLoader
from scaler.const import DEBUG
from sprites.sprite_types import SpriteType


class Renderer:
    """ A composable sprite renderer that can be used by a sprite manager (or standalone)
    to render sprites in different ways. """

    def __init__(self, display):
        self.display = display
        self.sprite_images = []
        self.sprite_palettes = []
        
    def load_img_and_scale(self, meta, sprite_type, prescale=True):
        sprite_type = str(sprite_type)

        orig_img = ImageLoader.load_image(
            filename=meta.image_path,
            frame_width=meta.width,
            frame_height=meta.height,
            prescale=prescale
        )

        frames = []
        num_frames = meta.num_frames

        if not prescale:
            num_frames = 1

        if DEBUG:
            print(f"Creating {num_frames} prescaled frames")

        for f in range(1, num_frames):
            """ Create prescaled frames from small(0.01%) to biggest (100%) """
            scale = f / num_frames  # Avoid division by zero

            new_width = math.ceil(meta.width * scale)
            new_height = math.ceil(meta.height * scale)

            new_frame = self.scale_frame(orig_img, new_width, new_height, meta.color_depth)
            frames.append(new_frame)

        frames.append(orig_img)  # Add original image as the last frame

        """Do we need to add upscale frames? (scale > 1)"""
        if ((meta.stretch_width and meta.stretch_width > meta.width) or
                (meta.stretch_height and meta.stretch_height > meta.height)):

            width_gap = meta.stretch_width - meta.width
            height_gap = meta.stretch_height - meta.height

            add_width_frames = 0
            add_height_frames = 0

            if width_gap > height_gap:
                add_width_frames = max(width_gap, height_gap)
            else:
                add_height_frames = max(width_gap, height_gap)

            for f in range(0, add_width_frames):
                pass

            for f in range(0, add_height_frames):
                pass

        self.sprite_palettes[sprite_type] = orig_img.palette
        meta.palette = orig_img.palette
        self.set_alpha_color(meta)

        return frames

    def do_blit(self, x: int, y: int, display: FrameBuffer, frame, palette, alpha=None):
        if alpha is not None:
            display.blit(frame, x, y, alpha, palette)
        else:
            display.blit(frame, x, y, -1, palette)

        return True

    def set_alpha_color(self, sprite_type: SpriteType):
        """Get the value of the color to be used as an alpha channel when drawing the sprite
        into the display framebuffer """

        if sprite_type.alpha_index in(None, -1):
            return False

        alpha_color = sprite_type.palette.get_bytes(sprite_type.alpha_index)
        sprite_type.alpha_color = alpha_color
