import math

from colors.framebuffer_palette import FramebufferPalette
from scaler.const import DEBUG, INK_GREEN, INK_YELLOW, DEBUG_INST
from scaler.scaler_debugger import printc
from scaler.sprite_scaler import SpriteScaler
from sprites.renderer_base import Renderer
from sprites.sprite_registry import registry
from sprites.sprite_types import SpriteType as types, FLAG_VISIBLE, FLAG_BLINK_FLIP, FLAG_BLINK
from profiler import timed

class RendererScaler(Renderer):
    """ A composable sprite renderer that can be used by a sprite manager (or standalone)
    to render sprites in different ways. """
    def __init__(self, display):
        super().__init__(display)
        self.scaler = SpriteScaler(display)
        self.min_scale = 0.064

    # @DEPRECATED
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

    @timed
    def render_sprite(self, inst, meta, images, palette):
        """
        Renders a sprite instance using on-the-fly scaling.
        sprite_inst: The uctypes struct for the sprite.
        camera_for_transform: Not directly used by this 2D scaler, but could be for draw_x/y calcs.
        """
        type_id = inst.sprite_type
        meta = registry.get_metadata(type_id)
        img_asset = registry.get_img(type_id)  # This should be a single Image object

        if not meta or not img_asset:
            if DEBUG:
                printc(f"RendererScaler: Assets not found for type_id {type_id}", INK_GREEN)
            return False

        if not types.get_flag(inst, FLAG_VISIBLE):
            if DEBUG: printc(f"RendererScaler: Sprite {type_id} invisible (flag).", INK_GREEN)
            return False

        if types.get_flag(inst, FLAG_BLINK):
            if types.get_flag(inst, FLAG_BLINK_FLIP):  # Assuming 1 = invisible part of blink
                if DEBUG: printc(f"RendererScaler: Sprite {type_id} blinked off.", INK_GREEN)
                return False

        if not inst.scale or inst.scale < self.min_scale:
            inst.scale = self.min_scale

        draw_scale = inst.scale
        if DEBUG_INST:
            printc(f"Rendering sprite at scale {draw_scale}x", INK_YELLOW)

        if meta.repeats < 2:
            self.scaler.draw_sprite(meta, img_asset, inst.draw_x, inst.draw_y, h_scale=draw_scale, v_scale=draw_scale)
        else:
            original_draw_x = inst.draw_x  # Save original for repeated sprites
            for i in range(meta.repeats):

                # Adjust draw_x for repeated sprites.
                current_draw_x = original_draw_x + (meta.repeat_spacing * draw_scale * i)

                # This is hacky and should be rewritten
                inst.draw_x = int(current_draw_x)
                self.scaler.draw_sprite(meta, img_asset, inst.draw_x, inst.draw_y, h_scale=draw_scale, v_scale=draw_scale)
            inst.draw_x = original_draw_x  # Restore original draw_x

        return True
