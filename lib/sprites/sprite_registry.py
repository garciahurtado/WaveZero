# sprite_registry.py
import math
import framebuf  # Required for buffer_format constants if passed to scaler
from images.image_loader import ImageLoader  # Ensure this path is correct
from images.indexed_image import Image, create_image  # Ensure this path is correct
from scaler.const import INK_YELLOW, DEBUG
from scaler.scaler_debugger import printc
from sprites.sprite_types import SpriteType  # Ensure this path is correct
# Import the new, more efficient scaling function that returns a FrameBuffer
from images.image_scaler import generate_scaled_framebuffer  # Make sure image_scaler.py has this function


class SpriteRegistry:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # Ensure __init__ logic runs only once
        if hasattr(self, '_is_initialized') and self._is_initialized:
            return

        self.sprite_metadata = {}  # Stores SpriteType objects (metadata)
        # Stores a single Image object per type_id.
        # For prescaled images, Image.frames will be a list of FrameBuffer objects.
        self.sprite_images = {}
        self.sprite_palettes = {}  # Stores Palette objects
        self._is_initialized = True  # Mark as initialized

    def add_type(self, type_id, sprite_class, prescale: bool = False, **kwargs):
        """
        Registers a sprite type by extracting 'sprite_type' (type_id) and
        'sprite_class' from kwargs. Instantiates 'sprite_class' with remaining
        kwargs and loads assets.
        """
        if DEBUG:
            printc(f"{sprite_class} sprite registered as ID: {type_id}", INK_YELLOW)

        # Remaining kwargs are override_kwargs for the sprite_class constructor
        override_kwargs = kwargs
        if not isinstance(sprite_class, type) or not issubclass(sprite_class, SpriteType):
            raise TypeError(f"sprite_class argument must be a class derived from SpriteType. Got: {sprite_class}")

        if type_id in self.sprite_metadata:
            # Using f-string for print, assuming printc is for colored output not available here
            print(f"Warning: Sprite type {type_id} already registered. Overwriting for class {sprite_class.__name__}.")

        meta_instance = sprite_class(**override_kwargs)

        self.sprite_metadata[type_id] = meta_instance
        meta = meta_instance

        if not all(hasattr(meta, attr) for attr in ['image_path', 'width', 'height', 'color_depth']):
            raise AttributeError(
                f"Metadata instance for type {type_id} (class {sprite_class.__name__}) is missing essential attributes (image_path, width, height, or color_depth). Ensure they are class attributes or passed in override_kwargs.")

        if not hasattr(meta, 'num_frames'):
            meta.num_frames = 1

        base_img_obj = ImageLoader.load_image(
            filename=meta.image_path,
            frame_width=meta.width,
            frame_height=meta.height,
            color_depth=meta.color_depth
        )

        if not base_img_obj or not base_img_obj.pixels:
            print(f"Error loading base image for type {type_id} ({meta.image_path}). Assets may be incomplete.")
            self.sprite_images[type_id] = None
            self.sprite_palettes[type_id] = None
            return

        self.sprite_palettes[type_id] = base_img_obj.palette
        meta.palette = base_img_obj.palette

        has_predefined_alpha_color = hasattr(meta, 'alpha_color') and meta.alpha_color is not None

        if hasattr(meta, 'alpha_index') and meta.alpha_index is not None and meta.alpha_index != -1 and meta.palette:
            try:
                meta.alpha_color = meta.palette.get_bytes(meta.alpha_index)
            except Exception as e:
                print(f"Warning: Could not get alpha_color for type {type_id} from alpha_index: {e}")
                if not has_predefined_alpha_color:
                    meta.alpha_color = None
        elif not has_predefined_alpha_color:
            meta.alpha_color = None

        if prescale:
            prescaled_framebuffers = []
            num_total_levels = meta.num_frames

            if meta.color_depth == 1:
                base_buffer_format = framebuf.MONO_HMSB
            elif meta.color_depth == 2:
                base_buffer_format = framebuf.GS2_HMSB
            elif meta.color_depth == 4:
                base_buffer_format = framebuf.GS4_HMSB
            elif meta.color_depth == 8:
                base_buffer_format = framebuf.GS8
            elif meta.color_depth == 16:
                base_buffer_format = framebuf.RGB565
            else:
                raise ValueError(f"Unsupported meta.color_depth {meta.color_depth} for prescaling type {type_id}")

            if num_total_levels <= 0:
                if base_img_obj.pixels: prescaled_framebuffers.append(base_img_obj.pixels)
            else:
                for i in range(1, num_total_levels):
                    scale_factor = i / num_total_levels
                    target_w = math.ceil(meta.width * scale_factor)
                    target_h = math.ceil(meta.height * scale_factor)

                    if meta.color_depth == 4 and target_w > 0 and target_w % 2 != 0:
                        target_w += 1
                    elif meta.color_depth == 2 and target_w > 0 and target_w % 4 != 0:
                        target_w = ((target_w + 3) // 4) * 4
                    elif meta.color_depth == 1 and target_w > 0 and target_w % 8 != 0:
                        target_w = ((target_w + 7) // 8) * 8

                    target_w = max(1, target_w)
                    target_h = max(1, target_h)

                    if target_w > 0 and target_h > 0:
                        scaled_fb = generate_scaled_framebuffer(
                            orig_img_pixels=base_img_obj.pixels,
                            orig_width=meta.width, orig_height=meta.height,
                            target_w=int(target_w), target_h=int(target_h),
                            color_depth=meta.color_depth, buffer_format=base_buffer_format
                        )
                        if scaled_fb: prescaled_framebuffers.append(scaled_fb)

                if base_img_obj.pixels: prescaled_framebuffers.append(base_img_obj.pixels)

            if not prescaled_framebuffers and base_img_obj.pixels:
                prescaled_framebuffers.append(base_img_obj.pixels)

            final_image_asset = create_image(
                width=meta.width, height=meta.height,
                pixels=base_img_obj.pixels, pixel_bytes=base_img_obj.pixel_bytes,
                pixel_bytes_addr=base_img_obj.pixel_bytes_addr,
                palette=base_img_obj.palette, palette_bytes=base_img_obj.palette_bytes,
                color_depth=meta.color_depth, frames=prescaled_framebuffers
            )
            self.sprite_images[type_id] = final_image_asset
        else:
            self.sprite_images[type_id] = base_img_obj

        # print(f"Assets loaded for type_id: {type_id} ({sprite_class.__name__})")

    # REMOVE the load_images method entirely if add_type handles all loading
    def _load_images(self, type_id: int, prescale: bool = False):
        """
        Loads the image and palette for a registered sprite type.
        If prescale is True, it generates multiple scaled FrameBuffer objects
        and stores them in the .frames attribute of the single Image object for this type.
        """
        if type_id not in self.sprite_metadata:
            raise ValueError(f"Sprite type {type_id} not registered with add_type() first.")

        meta = self.sprite_metadata[type_id]
        # Load the base image (this is an Image object from BMPReader)
        base_img_obj = ImageLoader.load_image(
            filename=meta.image_path,
            frame_width=meta.width,  # Used by BMPReader if it's a spritesheet
            frame_height=meta.height,  # Used by BMPReader if it's a spritesheet
            color_depth=meta.color_depth  # BPP, used by BMPReader
        )

        if not base_img_obj or not base_img_obj.pixels:  # Check base image and its primary pixel buffer
            print(f"Error loading base image or its pixel data for type {type_id} from {meta.image_path}")
            self.sprite_images[type_id] = None
            self.sprite_palettes[type_id] = None
            return

        # Store palette from the base image and update meta
        self.sprite_palettes[type_id] = base_img_obj.palette
        meta.palette = base_img_obj.palette  # Keep direct ref on meta for convenience

        # Set alpha color on the metadata object
        if meta.alpha_index is not None and meta.alpha_index != -1 and meta.palette:
            try:
                meta.alpha_color = meta.palette.get_bytes(meta.alpha_index)
            except Exception as e:
                print(f"Warning: Could not get alpha_color for type {type_id} from palette: {e}")
                meta.alpha_color = None
        else:
            meta.alpha_color = None

        if prescale:
            prescaled_framebuffers = []  # This will hold FrameBuffer objects
            num_total_levels = meta.num_frames  # How many scale levels desired (incl. original)

            # Determine the framebuf.FORMAT constant from meta.color_depth (BPP)
            # This is needed by generate_scaled_framebuffer
            if meta.color_depth == 1:
                base_buffer_format = framebuf.MONO_HMSB
            elif meta.color_depth == 2:
                base_buffer_format = framebuf.GS2_HMSB
            elif meta.color_depth == 4:
                base_buffer_format = framebuf.GS4_HMSB
            elif meta.color_depth == 8:
                base_buffer_format = framebuf.GS8
            elif meta.color_depth == 16:
                base_buffer_format = framebuf.RGB565
            else:
                raise ValueError(f"Unsupported meta.color_depth {meta.color_depth} for prescaling type {type_id}")

            if num_total_levels <= 0:
                print(
                    f"Warning: prescale=True for type {type_id} but meta.num_frames ({num_total_levels}) is unsuitable. Using original FrameBuffer only.")
                prescaled_framebuffers.append(base_img_obj.pixels)
            else:
                # Create (num_total_levels - 1) smaller versions
                for i in range(1, num_total_levels):  # Iterate for each smaller scaled version
                    scale_factor = i / num_total_levels
                    # Calculate target dimensions for this scale level
                    target_w = math.ceil(meta.width * scale_factor)
                    target_h = math.ceil(meta.height * scale_factor)

                    # Ensure target_w is valid for the color depth before calling scaler
                    if meta.color_depth == 4 and target_w > 0 and target_w % 2 != 0:
                        target_w += 1
                    elif meta.color_depth == 2 and target_w > 0 and target_w % 4 != 0:
                        target_w = ((target_w + 3) // 4) * 4
                    elif meta.color_depth == 1 and target_w > 0 and target_w % 8 != 0:
                        target_w = ((target_w + 7) // 8) * 8

                    target_w = max(1, target_w)  # Ensure dimensions are at least 1
                    target_h = max(1, target_h)

                    if target_w > 0 and target_h > 0:
                        # Call the function that returns just a FrameBuffer
                        scaled_fb = generate_scaled_framebuffer(
                            orig_img_pixels=base_img_obj.pixels,  # Source FrameBuffer
                            orig_width=meta.width,  # Source dimensions
                            orig_height=meta.height,
                            target_w=int(target_w),  # Target dimensions
                            target_h=int(target_h),
                            color_depth=meta.color_depth,  # BPP
                            buffer_format=base_buffer_format  # framebuf.FORMAT constant
                        )
                        if scaled_fb:
                            prescaled_framebuffers.append(scaled_fb)
                        else:
                            # generate_scaled_framebuffer should raise an error if it fails critically
                            print(
                                f"Warning: generate_scaled_framebuffer call did not return a FrameBuffer for {type_id} at factor {scale_factor}")
                    else:
                        print(
                            f"Warning: Calculated prescale dimensions for {type_id} at factor {scale_factor} are too small ({target_w}x{target_h}). Skipping this level.")

                # Add the original (largest) FrameBuffer as the last one in the list
                prescaled_framebuffers.append(base_img_obj.pixels)

            # If, after all attempts, the list is empty but the base image was valid, add base image's FrameBuffer
            if not prescaled_framebuffers and base_img_obj.pixels:
                prescaled_framebuffers.append(base_img_obj.pixels)

            # Create ONE final Image object for the registry.
            # Its .frames attribute will hold the list of scaled FrameBuffer objects.
            # Its .pixels attribute can point to the largest/original FrameBuffer for consistency,
            # or the first one if preferred (though .frames is the primary access for prescaled).
            final_image_asset = create_image(
                width=meta.width,  # Width of the original/largest version
                height=meta.height,  # Height of the original/largest version
                pixels=base_img_obj.pixels,  # Primary pixel buffer (e.g., original size)
                pixel_bytes=base_img_obj.pixel_bytes,  # Backing bytes for primary pixel buffer
                pixel_bytes_addr=base_img_obj.pixel_bytes_addr,
                palette=base_img_obj.palette,
                palette_bytes=base_img_obj.palette_bytes,
                color_depth=meta.color_depth,  # BPP
                frames=prescaled_framebuffers  # List of FrameBuffer objects for each scale level
            )
            self.sprite_images[type_id] = final_image_asset
        else:
            # For non-prescaled, store the base_img_obj directly.
            # If it's a spritesheet, its .frames attribute (from BMPReader) contains animation FrameBuffers.
            self.sprite_images[type_id] = base_img_obj

    def get_metadata(self, type_id: int) -> SpriteType:
        """Gets the registered SpriteType metadata instance."""
        return self.sprite_metadata.get(type_id)

    def get_img(self, type_id: int) -> Image:  # Should always return a single Image object
        """
        Gets the Image object for the sprite type.
        If prescaled, access scaled FrameBuffers via returned_Image.frames[index].
        If animated spritesheet (not prescaled), access animation FrameBuffers via returned_Image.frames[index].
        If single static image (not prescaled), use returned_Image.pixels.
        """
        return self.sprite_images.get(type_id)

    def get_palette(self, type_id: int):  # Returns your Palette object
        """Gets the loaded palette for the sprite type."""
        return self.sprite_palettes.get(type_id)


# Global instance
registry = SpriteRegistry()
