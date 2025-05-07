import math

from uctypes import addressof

from colors.framebuffer_palette import FramebufferPalette
from images.image_loader import ImageLoader
from images.indexed_image import create_image
from scaler.const import DEBUG
from sprites.renderer_base import Renderer
from sprites.sprite_types import SpriteType as types, FLAG_VISIBLE, FLAG_BLINK_FLIP, FLAG_BLINK, SpriteType
from framebuf import FrameBuffer, GS4_HMSB, GS8

class RendererPrescaled(Renderer):
    def add_type(self, sprite_type, class_obj):
        loaded_frames = self.load_img_and_scale(class_obj, sprite_type, prescale=True)

        # Store the result (could be a list or single Image)
        self.sprite_images[sprite_type] = loaded_frames  # Store the whole list/Image

        # Get palette from the appropriate place (e.g., the first frame if it's a list)
        first_img = loaded_frames[0] if isinstance(loaded_frames, list) else loaded_frames
        if first_img:  # Check if loading succeeded
            self.sprite_palettes[sprite_type] = first_img.palette
            class_obj.palette = first_img.palette  # Also update meta palette
            self.set_alpha_color(class_obj)
        else:
            print(f"Warning: Failed to load image/frames for type {sprite_type}")
            # Handle error appropriately

    def scale_frame(self, orig_img, new_width, new_height, color_depth):
        if color_depth not in [4, 8]:
            raise ValueError(f"Unsupported color depth: {color_depth}")

        if new_width % 2 and color_depth == 4:  # Width must be even for 4-bit images
            new_width += 1

        byte_size = (new_width * new_height) // (8 // color_depth)
        new_bytes = bytearray(byte_size)
        new_bytes_addr = addressof(new_bytes)

        if color_depth == 4:
            buffer_format = GS4_HMSB
        else:  # 8-bit
            buffer_format = GS8

        new_buffer = FrameBuffer(new_bytes, new_width, new_height, buffer_format)

        x_ratio = orig_img.width / new_width
        y_ratio = orig_img.height / new_height

        for y in range(new_height):
            for x in range(0, new_width, 2 if color_depth == 4 else 1):
                x_1 = min(int(x * x_ratio), orig_img.width - 1)
                y_1 = min(int(y * y_ratio), orig_img.height - 1)

                color1 = orig_img.pixels.pixel(x_1, y_1)
                new_buffer.pixel(x, y, color1)

                if color_depth == 4:
                    x_2 = min(int((x + 1) * x_ratio), orig_img.width - 1)
                    color2 = orig_img.pixels.pixel(x_2, y_1)
                    new_buffer.pixel(x + 1, y, color2)

        return create_image(new_width, new_height, new_buffer, new_bytes, new_bytes_addr,
                            orig_img.palette, orig_img.palette_bytes, color_depth)

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
