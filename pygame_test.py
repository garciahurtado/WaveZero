import pygame
from road_grid import RoadGrid

# Initialize Pygame
pygame.init()

# Set the window size
width = 96
height = 64
screen = pygame.display.set_mode((width, height))
pygame.display.set_caption("Horizon Perspective")

# Set the frame rate
clock = pygame.time.Clock()
fps = 30

# Set the colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)

# Set the initial line positions and speeds
lines = []
num_lines = 10
for i in range(num_lines):
    y = i * (height // num_lines)
    speed = (i + 1) * 0.5
    lines.append([y, speed])

# Game loop
running = True
while running:
    # Handle events
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    # Clear the screen
    screen.fill(BLACK)

    # Update and draw the lines
    for i in range(num_lines):
        lines[i][0] += lines[i][1]  # Update the line position
        if lines[i][0] > height:
            lines[i][0] = 0  # Reset the line position when it reaches the bottom

        # Calculate the line length based on perspective
        line_length = width * (lines[i][0] / height)

        # Calculate the line position to center it horizontally
        line_pos = (width - line_length) // 2

        # Draw the line
        pygame.draw.line(screen, WHITE, (line_pos, lines[i][0]), (line_pos + line_length, lines[i][0]))

    # Update the display
    pygame.display.flip()

    # Set the frame rate
    clock.tick(fps)

# Quit Pygame
pygame.quit()