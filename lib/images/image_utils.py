# image_processing_utils.py
import math
import uctypes
import framebuf
from images.indexed_image import create_image, Image  # Adjust path if needed


def scale_indexed_img(orig_img: Image, new_width: int, new_height: int) -> Image:
    """
    Scales an indexed image using nearest-neighbor sampling.
    The new image will have the same color depth and palette as the original.
    Assumes orig_img.pixels is a FrameBuffer of the source image data.
    """
    color_depth = orig_img.color_depth

    if color_depth not in [4, 8]:
        raise ValueError(f"Unsupported color depth for scaling: {color_depth}")

    if new_width <= 0 or new_height <= 0:
        # Return a minimal valid image or raise error, depending on desired handling
        print(f"Error: Cannot scale to zero or negative size ({new_width}x{new_height}).")
        # Optionally, create a 1x1 or 2x2 blank image of the correct depth
        min_dim = 1 if color_depth == 8 else 2
        if new_width <= 0: new_width = min_dim
        if new_height <= 0: new_height = min_dim
        # Fall through to create this minimal image

    # Ensure width is even for 4-bit images if it's a valid width
    if color_depth == 4 and new_width > 0 and new_width % 2 != 0:
        new_width += 1

    # Calculate byte size for the new image buffer
    if new_width == 0 or new_height == 0:  # Should ideally not happen if min_dim applied
        byte_size = 0
    elif color_depth == 4:
        byte_size = (new_width * new_height) // 2
    else:  # color_depth == 8
        byte_size = new_width * new_height

    new_pixel_bytes = bytearray(byte_size if byte_size > 0 else 1)  # Ensure bytearray not size 0
    if byte_size == 0 and new_width > 0 and new_height > 0:  # Recalc if initial byte_size was 0 but dims are not
        if color_depth == 4:
            byte_size = (new_width * new_height) // 2
        else:
            byte_size = new_width * new_height
        new_pixel_bytes = bytearray(byte_size)

    new_pixel_bytes_addr = uctypes.addressof(new_pixel_bytes)
    buffer_format = framebuf.GS4_HMSB if color_depth == 4 else framebuf.GS8

    # Ensure FrameBuffer can be created with the dimensions
    if new_width == 0 or new_height == 0:  # Cannot create FB with zero dimension
        # This case indicates an issue, possibly return a pre-defined minimal image or error
        # For now, let's assume the caller (SpriteRegistry) ensures valid dimensions for scaling.
        # If we reach here with new_width/new_height = 0, it's an issue.
        # Create a dummy 1x1 or 2x1 FrameBuffer
        dummy_w = 2 if color_depth == 4 else 1
        dummy_h = 1
        dummy_byte_size = (dummy_w * dummy_h) // (8 // color_depth)
        dummy_bytes = bytearray(dummy_byte_size)
        new_framebuf = framebuf.FrameBuffer(dummy_bytes, dummy_w, dummy_h, buffer_format)
        print(f"Warning: scaling produced 0 dimension, returning dummy {dummy_w}x{dummy_h} image.")
        return create_image(
            dummy_w, dummy_h, new_framebuf, dummy_bytes, uctypes.addressof(dummy_bytes),
            orig_img.palette, orig_img.palette_bytes, color_depth
        )

    new_framebuf = framebuf.FrameBuffer(new_pixel_bytes, new_width, new_height, buffer_format)

    if orig_img.width == 0 or orig_img.height == 0:  # Source image is invalid
        # Fill new_framebuf with 0s (transparent or first palette color)
        for i in range(len(new_pixel_bytes)): new_pixel_bytes[i] = 0
    else:
        x_ratio = orig_img.width / new_width
        y_ratio = orig_img.height / new_height

        for y_coord in range(new_height):
            orig_y = min(int(y_coord * y_ratio), orig_img.height - 1)

            if color_depth == 4:
                for x_coord_pair_start in range(0, new_width, 2):
                    orig_x1 = min(int(x_coord_pair_start * x_ratio), orig_img.width - 1)
                    color1 = orig_img.pixels.pixel(orig_x1, orig_y)
                    new_framebuf.pixel(x_coord_pair_start, y_coord, color1)

                    if x_coord_pair_start + 1 < new_width:
                        orig_x2 = min(int((x_coord_pair_start + 1) * x_ratio), orig_img.width - 1)
                        color2 = orig_img.pixels.pixel(orig_x2, orig_y)
                        new_framebuf.pixel(x_coord_pair_start + 1, y_coord, color2)
            else:  # color_depth == 8
                for x_coord in range(new_width):
                    orig_x = min(int(x_coord * x_ratio), orig_img.width - 1)
                    color = orig_img.pixels.pixel(orig_x, orig_y)
                    new_framebuf.pixel(x_coord, y_coord, color)

    return create_image(
        new_width, new_height, new_framebuf, new_pixel_bytes, new_pixel_bytes_addr,
        orig_img.palette, orig_img.palette_bytes, color_depth
    )