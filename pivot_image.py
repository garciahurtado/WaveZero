from PIL import Image
import sys
import os

# Check if the correct number of command-line arguments are provided
if len(sys.argv) != 4:
    print("Usage: python rearrange_spritesheet.py <folder_name/image_name> <frame_width> <frame_height>")
    sys.exit(1)

# Get the command-line arguments
image_path = sys.argv[1]
frame_width = int(sys.argv[2])
frame_height = int(sys.argv[3])

# Open the spritesheet image
spritesheet = Image.open(image_path)

# Get the width and height of the spritesheet
width, height = spritesheet.size

# Calculate the number of frames in the spritesheet
num_frames = width // frame_width

# Create a new image for the rearranged spritesheet
new_spritesheet = Image.new('RGBA', (frame_width, num_frames * frame_height))

# Rearrange the frames from left to right to top to bottom
for i in range(num_frames):
    frame = spritesheet.crop((i * frame_width, 0, (i + 1) * frame_width, frame_height))
    new_spritesheet.paste(frame, (0, i * frame_height))

# Save the rearranged spritesheet
folder_name, image_name = os.path.split(image_path)
new_image_path = os.path.join(folder_name, 'rearranged_' + image_name)
new_spritesheet.save(new_image_path)