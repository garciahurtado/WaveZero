#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os, re, glob
from gimpfu import *
from gimpenums import *

def export_rgb(image, drawable, output_path):
    try:
        width = drawable.width
        height = drawable.height
        pixel_regions = drawable.get_pixel_rgn(0, 0, width, height, False, False)
        pixels = pixel_regions[:, :]

        with open(output_path, 'w') as f:
            for y in range(height):
                for x in range(width):
                    r, g, b = pixels[x * 3 + y * width * 3: x * 3 + y * width * 3 + 3]
                    f.write(f"[{r},{g},{b}]\n")

        pdb.gimp_message("RGB export completed successfully!")
    except Exception as e:
        error_msg = f"An error occurred: {str(e)}\n{e.format_exc()}"
        pdb.gimp_message(error_msg)


register(
    "export_rgb_txt",
    "Export RGB values",
    "Exports RGB values of an image to a text file",
    "Your Name",
    "Your Name",
    "2023",
    "<Image>/MyScripts/Export RGB to TXT",
    "*",
    [
        (PF_FILENAME, "output_path", "Save to", ""),
    ],
    [],
    export_rgb)

main()