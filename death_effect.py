from displayio import Group, Bitmap, TileGrid, Palette, ColorConverter
import math

def create_particles(bitmap, root):

    # Create the TileGrid to hold the bitmap
    grid = TileGrid(bitmap, pixel_shader=ColorConverter(), x=0, y=0)

    # Add the TileGrid to the display graph
    root.append(grid)

    # Get the center of the bitmap
    center_x = bitmap.screen_width // 2
    center_y = bitmap.screen_height // 2

    # Create a list to store particle data
    particles = []

    # Get the particle data from the bitmap
    for x in range(0,20):
        for y in range(0,20):
            if bitmap[x, y] != 0:
                # Calculate the distance from the center
                distance = math.sqrt((x - center_x) ** 2 + (y - center_y) ** 2)

                # Calculate the angle from the center
                angle = math.atan2(y - center_y, x - center_x)

                # Store the particle data as a tuple
                particles.append((x, y, distance, angle))

    return particles, grid

def anim_particles(particles, display, grid):
    # Animate the particles
    while True:
        # Create a new TileGrid to hold the updated particle positions
        #new_tile_grid = TileGrid(bitmap.width, bitmap.height, pixel_shader=ColorConverter(), x=0, y=0)

        for i in range(len(particles)):
            x, y, distance, angle = particles[i]

            # Calculate the new position
            x += math.cos(angle) * distance / 10
            y += math.sin(angle) * distance / 10

            # Store the updated particle data
            particles[i] = (x, y, distance, angle)

            # Update the new TileGrid with the new position
            grid[int(x), int(y)] = 0xFFFFFF

        # Set the display to show the new TileGrid
        display.show(grid)