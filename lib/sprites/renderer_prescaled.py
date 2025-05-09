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
    # @DEPRECATED
    def add_type(self, sprite_type, class_obj):
        raise DeprecationWarning
        loaded_frames = self.load_img_and_scale(class_obj, sprite_type, prescale=True)

        # Store the result (could be a list or single Image)
        # self.sprite_images[sprite_type] = loaded_frames  # Store the whole list/Image

        # Get palette from the appropriate place (e.g., the first frame if it's a list)
        first_img = loaded_frames[0] if isinstance(loaded_frames, list) else loaded_frames
        if first_img:  # Check if loading succeeded
            # self.sprite_palettes[sprite_type] = first_img.palette
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
        """
               Renders a sprite instance using pre-scaled images from the SpriteRegistry.
               sprite_inst: The uctypes struct for the sprite.
               camera_for_transform: Not directly used here for blitting, but affects sprite_inst.draw_x/y/scale.
               """
        type_id = sprite_inst.sprite_type
        meta = sprite_registry.get_metadata(type_id)

        # For prescaled, get_img returns a LIST of Image objects
        scaled_image_list = sprite_registry.get_img(type_id)
        palette = sprite_registry.get_palette(type_id)

        if not meta or not scaled_image_list or not palette:
            if DEBUG:
                print(f"RendererPrescaled: Assets not found for type_id {type_id}")
            return False

        if not isinstance(scaled_image_list, list) or not scaled_image_list:
            if DEBUG:
                print(
                    f"RendererPrescaled: Expected a list of prescaled images for type {type_id}, got {type(scaled_image_list)}")
            return False

        # Visibility and blink flags
        if not types_meta.get_flag(sprite_inst, FLAG_VISIBLE):
            if DEBUG: print(f"RendererPrescaled: Sprite {type_id} invisible (flag).")
            return False
        if types_meta.get_flag(sprite_inst, FLAG_BLINK) and types_meta.get_flag(sprite_inst, FLAG_BLINK_FLIP):
            if DEBUG: print(f"RendererPrescaled: Sprite {type_id} blinked off.")
            return False

        # Determine which prescaled frame to use.
        # This depends on how sprite_inst.current_frame or sprite_inst.scale maps to the list.
        # If sprite_inst.scale (0.0 to 1.0+) needs to map to an index:
        #   num_scaled_frames = len(scaled_image_list)
        #   scale_index = min(int(sprite_inst.scale * (num_scaled_frames -1)), num_scaled_frames - 1)
        #   image_to_blit = scaled_image_list[scale_index]
        # If sprite_inst.current_frame directly refers to the prescaled image index (e.g., for different LODs):
        frame_index = sprite_inst.current_frame  # Assuming current_frame is the index for the prescaled list

        if not (0 <= frame_index < len(scaled_image_list)):
            if DEBUG:
                print(
                    f"RendererPrescaled: Invalid frame_index {frame_index} for {len(scaled_image_list)} prescaled images (type {type_id}). Defaulting to 0.")
            frame_index = 0  # Fallback to the first prescaled image
            if not scaled_image_list: return False  # Should have been caught earlier

        image_to_blit = scaled_image_list[frame_index]  # This is an Image object

        if not image_to_blit or not image_to_blit.pixels:
            if DEBUG: print(
                f"RendererPrescaled: Selected image or its pixel data is invalid for type {type_id}, frame {frame_index}.")
            return False

        frame_buffer_to_blit = image_to_blit.pixels  # This is a FrameBuffer
        alpha_color = meta.alpha_color if hasattr(meta, 'alpha_color') else -1

        # Handle sprite repeating (horizontal clones)
        if meta.repeats < 2:
            self.do_blit(
                x=int(sprite_inst.draw_x),
                y=int(sprite_inst.draw_y),
                frame=frame_buffer_to_blit,
                palette=palette,
                alpha=alpha_color
            )
        else:
            # For repeated sprites, the scale used for spacing should be the sprite's current visual scale,
            # which might be implicitly represented by the chosen prescaled frame's size relative to original.
            # Or, use sprite_inst.scale if that's the 'logical' scale.
            # Let's assume sprite_inst.scale is the correct factor for spacing.
            effective_scale_for_spacing = sprite_inst.scale
            for i in range(meta.repeats):
                # repeat_spacing is likely defined in original pixels.
                # The spacing needs to be adjusted by the current effective scale of the sprite.
                x_offset = meta.repeat_spacing * effective_scale_for_spacing * i
                current_draw_x = sprite_inst.draw_x + x_offset

                self.do_blit(
                    x=int(current_draw_x),
                    y=int(sprite_inst.draw_y),
                    frame=frame_buffer_to_blit,
                    palette=palette,
                    alpha=alpha_color
                )

                # Used to be:
                # """Also draw horizontal clones of this sprite, if needed """
                # for i in range(0, meta.repeats):
                #     x = start_x + (meta.repeat_spacing * sprite.scale * i)
                #     self.do_blit(x=round(x), y=start_y, display=self.display, frame=image.pixels, palette=palette,
                #                  alpha=alpha)
        return True
