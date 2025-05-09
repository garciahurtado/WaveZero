# image_scaler.py
import math
import uctypes  # For addressof
import framebuf  # For FrameBuffer, GS4_HMSB, GS8
from images.indexed_image import create_image, Image  # Ensure path is correct
from scaler.const import INK_CYAN, INK_RED # Assuming INK_RED is defined for debugging
from scaler.scaler_debugger import printc


def generate_scaled_framebuffer(orig_img_pixels: framebuf.FrameBuffer,
                                orig_width: int, orig_height: int,
                                target_w: int, target_h: int,
                                color_depth: int, buffer_format: int) -> framebuf.FrameBuffer:
    """
    Generates a new FrameBuffer containing a scaled version of the original pixel data.

    Args:
        orig_img_pixels: The source FrameBuffer object to scale.
        orig_width: Width of the source FrameBuffer.
        orig_height: Height of the source FrameBuffer.
        target_w: Target width for the new scaled FrameBuffer.
        target_h: Target height for the new scaled FrameBuffer.
        color_depth: Bits per pixel (1, 2, 4, 8, 16).
        buffer_format: The framebuf.FORMAT constant (e.g., framebuf.GS4_HMSB).

    Returns:
        A new framebuf.FrameBuffer object with the scaled image.
        The caller is responsible for managing the lifecycle of the backing bytearray
        if it's not tied directly to the returned FrameBuffer's scope.
        However, FrameBuffer typically takes ownership or a reference.
    """

    # Calculate byte_size for the new FrameBuffer based on target dimensions and color_depth
    if color_depth == 1: actual_byte_size = (target_w * target_h + 7) // 8
    elif color_depth == 2: actual_byte_size = (target_w * target_h + 3) // 4
    elif color_depth == 4: actual_byte_size = (target_w * target_h + 1) // 2
    elif color_depth == 8: actual_byte_size = target_w * target_h
    elif color_depth == 16: actual_byte_size = target_w * target_h * 2
    else:
        raise ValueError(f"Cannot calculate byte_size for color_depth: {color_depth}")

    if actual_byte_size <= 0:
        # This case should ideally be prevented by target_w/h validation before calling
        printc(f"Error: byte_size is {actual_byte_size} for {target_w}x{target_h} depth {color_depth}", INK_RED)
        # Create a minimal valid bytearray and adjust dimensions if necessary
        if color_depth == 4: target_w, target_h, actual_byte_size = 2, 1, 1
        elif color_depth == 8: target_w, target_h, actual_byte_size = 1, 1, 1
        else: raise ValueError("Cannot create fallback for zero byte_size with this depth")
        printc(f"Fallback to: {target_w}x{target_h}, size {actual_byte_size}", INK_RED)


    new_pixel_bytes = bytearray(actual_byte_size)
    # The FrameBuffer will use this bytearray.
    # The bytearray must live as long as the FrameBuffer is in use.

    try:
        new_fb = framebuf.FrameBuffer(new_pixel_bytes, target_w, target_h, buffer_format)
    except Exception as e:
        printc(f"Error creating new FrameBuffer: {target_w}x{target_h}, format {buffer_format}, bytes {len(new_pixel_bytes)}", INK_RED)
        raise e

    # Scaling logic (nearest neighbor)
    if orig_width > 0 and orig_height > 0:
        x_ratio = orig_width / target_w
        y_ratio = orig_height / target_h

        for y_coord in range(target_h):
            orig_y = min(int(y_coord * y_ratio), orig_height - 1)

            if color_depth == 4: # Specific logic for 4-bit from your original code
                for x_coord_pair_start in range(0, target_w, 2):
                    src_x1 = min(int(x_coord_pair_start * x_ratio), orig_width - 1)
                    color1 = orig_img_pixels.pixel(src_x1, orig_y)
                    if color1 is None: # Debugging the TypeError
                        printc(f"CRITICAL: orig_img_pixels.pixel({src_x1}, {orig_y}) returned None for color1!", INK_RED)
                        color1 = 0 # Default to prevent crash, for debugging
                    new_fb.pixel(x_coord_pair_start, y_coord, color1)

                    if x_coord_pair_start + 1 < target_w:
                        src_x2 = min(int((x_coord_pair_start + 1) * x_ratio), orig_width - 1)
                        color2 = orig_img_pixels.pixel(src_x2, orig_y)
                        if color2 is None: # Debugging the TypeError
                            printc(f"CRITICAL: orig_img_pixels.pixel({src_x2}, {orig_y}) returned None for color2!", INK_RED)
                            color2 = 0 # Default to prevent crash
                        new_fb.pixel(x_coord_pair_start + 1, y_coord, color2)
            else:  # For 1, 2, 8, 16 bit
                for x_coord in range(target_w):
                    orig_x = min(int(x_coord * x_ratio), orig_width - 1)
                    color = orig_img_pixels.pixel(orig_x, orig_y)
                    if color is None: # Debugging the TypeError
                        printc(f"CRITICAL: orig_img_pixels.pixel({orig_x}, {orig_y}) returned None for color (non-4bit)!", INK_RED)
                        color = 0 # Default to prevent crash
                    new_fb.pixel(x_coord, y_coord, color)
    # else: Source image was 0-width or 0-height, new_fb remains blank.

    return new_fb


# Your original scale_img function (from uploaded file)
# This version returns a full Image object and is kept for reference or other uses.
# The TypeError debugging should be focused within this function if it's the one directly causing it.
def scale_img(orig_img: Image, new_width: int, new_height: int, color_depth: int) -> Image:
    """
    Scales an Image object based on the original scale_frame logic.
    orig_img: The source Image object (as returned by BMPReader).
    new_width, new_height: Target dimensions for the scaled image.
    color_depth: Bits per pixel (e.g., 4 for GS4_HMSB, 8 for GS8).
    Returns a new Image object representing the scaled version.
    This function is from your uploaded file and is where the TypeError was occurring.
    """
    if color_depth not in [1, 2, 4, 8, 16]:
        raise ValueError(f"Unsupported color depth: {color_depth}")

    target_w = max(1, int(new_width))
    target_h = max(1, int(new_height))

    if target_w % 2 != 0 and color_depth == 4:
        target_w += 1
    elif target_w % 4 != 0 and color_depth == 2:
        target_w = ((target_w + 3) // 4) * 4
    elif target_w % 8 != 0 and color_depth == 1:
        target_w = ((target_w + 7) // 8) * 8

    if color_depth == 1: actual_byte_size = (target_w * target_h + 7) // 8
    elif color_depth == 2: actual_byte_size = (target_w * target_h + 3) // 4
    elif color_depth == 4: actual_byte_size = (target_w * target_h + 1) // 2
    elif color_depth == 8: actual_byte_size = target_w * target_h
    elif color_depth == 16: actual_byte_size = target_w * target_h * 2
    else:
        raise ValueError(f"Cannot calculate byte_size for color_depth: {color_depth}")

    if actual_byte_size <= 0:
        printc(f"Error: byte_size is {actual_byte_size} for {target_w}x{target_h} depth {color_depth}", INK_RED)
        if color_depth == 4: target_w, target_h, actual_byte_size = 2, 1, 1
        elif color_depth == 8: target_w, target_h, actual_byte_size = 1, 1, 1
        else: raise ValueError("Cannot create fallback for zero byte_size with this depth")

    new_pixel_bytes = bytearray(actual_byte_size)
    new_pixel_bytes_addr = uctypes.addressof(new_pixel_bytes)

    if color_depth == 1: buffer_format = framebuf.MONO_HMSB
    elif color_depth == 2: buffer_format = framebuf.GS2_HMSB
    elif color_depth == 4: buffer_format = framebuf.GS4_HMSB
    elif color_depth == 8: buffer_format = framebuf.GS8
    elif color_depth == 16: buffer_format = framebuf.RGB565
    else:
        raise ValueError(f"No matching FrameBuffer format for color_depth: {color_depth}")

    try:
        new_fb = framebuf.FrameBuffer(new_pixel_bytes, target_w, target_h, buffer_format)
    except Exception as e:
        printc(f"Error creating new FrameBuffer: {target_w}x{target_h}, format {buffer_format}, bytes {len(new_pixel_bytes)}", INK_RED)
        raise e

    if orig_img.width > 0 and orig_img.height > 0:
        x_ratio = orig_img.width / target_w
        y_ratio = orig_img.height / target_h

        for y_coord in range(target_h):
            orig_y = min(int(y_coord * y_ratio), orig_img.height - 1)
            if color_depth == 4:
                for x_coord_pair_start in range(0, target_w, 2): # Renamed from x_coord
                    src_x1 = min(int(x_coord_pair_start * x_ratio), orig_img.width - 1)
                    color1 = orig_img.pixels.pixel(src_x1, orig_y)
                    if color1 is None: # Your original check was inside the non-4bit else block
                        printc(f"VALUE ERROR (color1): x={src_x1} y={orig_y} color={color1}", INK_RED)
                        # To debug the TypeError, you need to find out WHY color1 is None
                        # For now, to prevent crash during testing other parts:
                        # color1 = 0 # Or some other default valid color index
                        raise ValueError("Pixel color1 is None") # Or handle as an error
                    new_fb.pixel(x_coord_pair_start, y_coord, color1)

                    if x_coord_pair_start + 1 < target_w:
                        src_x2 = min(int((x_coord_pair_start + 1) * x_ratio), orig_img.width - 1)
                        color2 = orig_img.pixels.pixel(src_x2, orig_y)
                        if color2 is None:
                            printc(f"VALUE ERROR (color2): x={src_x2} y={orig_y} color={color2}", INK_RED)
                            # color2 = 0
                            raise ValueError("Pixel color2 is None")
                        new_fb.pixel(x_coord_pair_start + 1, y_coord, color2)
            else:
                for x_coord in range(target_w):
                    orig_x = min(int(x_coord * x_ratio), orig_img.width - 1)
                    color = orig_img.pixels.pixel(orig_x, orig_y)
                    # This is the check from your uploaded image_scaler.py
                    if x_coord is None or y_coord is None or color is None: # x_coord and y_coord will not be None here
                        printc(f"VALUE ERROR (color, non-4bit): x={orig_x} y={orig_y} color={color}", INK_RED)
                        # color = 0
                        raise ValueError("Pixel color is None (non-4bit path)")
                    new_fb.pixel(x_coord, y_coord, color)
    else:
        pass # Source image 0-width or 0-height

    printc(f"RETURNING WITH A NEW PIXEL BYTES: {new_pixel_bytes}", INK_CYAN)
    return create_image(
        target_w, target_h, new_fb, new_pixel_bytes, new_pixel_bytes_addr,
        orig_img.palette, orig_img.palette_bytes, orig_img.color_depth,
        frames=None
    )
