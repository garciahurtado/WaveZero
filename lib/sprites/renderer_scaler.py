import math

from colors.framebuffer_palette import FramebufferPalette
from scaler.const import DEBUG, INK_GREEN
from scaler.scaler_debugger import printc
from scaler.sprite_scaler import SpriteScaler
from sprites.renderer_base import Renderer
from sprites.sprite_registry import registry
from sprites.sprite_types import SpriteType as types, FLAG_VISIBLE, FLAG_BLINK_FLIP, FLAG_BLINK
from framebuf import FrameBuffer

class RendererScaler(Renderer):
    """ A composable sprite renderer that can be used by a sprite manager (or standalone)
    to render sprites in different ways. """
    def __init__(self, display):
        super().__init__(display)
        self.scaler = SpriteScaler(display)

    #@DEPRECATED
    def add_type(self, sprite_type, class_obj):
        raise DeprecationWarning

        loaded_frames = self.load_img_and_scale(class_obj, sprite_type, prescale=False)

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

    def render_sprite(self, inst, meta, images, palette):
        """
                Renders a sprite instance using on-the-fly scaling.
                sprite_inst: The uctypes struct for the sprite.
                camera_for_transform: Not directly used by this 2D scaler, but could be for draw_x/y calcs.
                """
        type_id = inst.sprite_type
        meta = registry.get_metadata(type_id)
        img_asset = registry.get_img(type_id)  # This should be a single Image object
        # Palette is fetched by SpriteScaler or can be passed if SpriteScaler API requires it.
        # For now, assume SpriteScaler can get it or it's part of meta/img_asset.

        if not meta or not img_asset:
            if DEBUG:
                printc(f"RendererScaler: Assets not found for type_id {type_id}", INK_GREEN)
            return False

        # Visibility and blink flags (from your original code)
        if not types.get_flag(inst, FLAG_VISIBLE):
            if DEBUG: printc(f"RendererScaler: Sprite {type_id} invisible (flag).", INK_GREEN)
            return False

        if types.get_flag(inst, FLAG_BLINK):
            # Assuming FLAG_BLINK_FLIP is handled by the sprite's update logic
            # to make it actually invisible every other frame based on blink_flip.
            # If blink_flip means "currently in off state of blink", then:
            if types.get_flag(inst, FLAG_BLINK_FLIP):  # Assuming 1 = invisible part of blink
                if DEBUG: printc(f"RendererScaler: Sprite {type_id} blinked off.", INK_GREEN)
                return False

        # The img_asset from SpriteRegistry (when prescale=False) is a single Image object.
        # If it's from a spritesheet, img_asset.frames is a list of FrameBuffers.
        # SpriteScaler needs a single FrameBuffer to scale.
        # We need to select the correct animation frame if the sprite is animated.

        # SpriteScaler's draw_sprite expects:
        # draw_sprite(self, sprite_meta, instance, image_to_scale, h_scale, v_scale)
        # where image_to_scale is an Image object.

        # Note: inst.scale is the calculated 3D scale.
        # SpriteScaler likely applies this.
        # inst.draw_x, inst.draw_y are screen coordinates.
        draw_scale = inst.scale
        if draw_scale < 0.125:
            draw_scale = 0.125

        # Handle sprite repeating (horizontal clones)
        if meta.repeats < 2:
            self.scaler.draw_sprite(
                meta,
                inst,
                img_asset,
                h_scale=draw_scale,  # Assuming inst.scale holds the desired final scale
                v_scale=draw_scale
            )
        else:
            original_draw_x = inst.draw_x  # Save original for repeated sprites
            for i in range(meta.repeats):
                # Adjust draw_x for repeated sprites.

                current_draw_x = original_draw_x + (meta.repeat_spacing * draw_scale * i)

                # This is hacky and should be rewritten
                inst.draw_x = round(current_draw_x)
                self.scaler.draw_sprite(
                    meta,
                    inst,
                    img_asset,
                    h_scale=draw_scale,
                    v_scale=draw_scale
                )
            inst.draw_x = original_draw_x  # Restore original draw_x

        return True
