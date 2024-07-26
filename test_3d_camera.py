import math


class Camera3D:
    def __init__(self, screen_width, screen_height, fov=60, horizon=150):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.aspect_ratio = screen_width / screen_height
        self.fov = math.radians(fov)
        self.horizon = horizon

        self.fov_factor = 1 / math.tan(self.fov / 2)

        self.camera_x = 0
        self.camera_y = -10  # Camera is 10 units back
        self.camera_z = 10  # Camera is 10 units up

    def to_2d_v2(self, x, y, z):
        # Translate point relative to camera
        x -= self.camera_x
        y -= self.camera_y
        z -= self.camera_z

        # Perspective projection for x
        if y != 0:
            screen_x = x / y * self.fov_factor
        else:
            screen_x = x * self.fov_factor * 1e6  # Arbitrarily large number

        # Adjust x for aspect ratio
        screen_x = screen_x / self.aspect_ratio

        # Convert x to screen coordinates
        screen_x = screen_x + self.screen_width / 2

        # Calculate z (vertical position) based on fixed horizon
        if y != 0:
            # Calculate the projected z position
            projected_z = z / y * self.fov_factor

            # Map the projected z to screen coordinates with fixed horizon
            screen_y = self.horizon  # Start at the horizon level
            screen_y -= (projected_z - self.horizon / y * self.fov_factor) * self.screen_height / (2 * self.fov_factor)
        else:
            # Handle case when y is 0 (point at infinity)
            screen_y = self.horizon if z >= self.horizon else self.screen_height

        # Clamp screen_y to be within the screen bounds
        screen_y = max(0, min(self.screen_height, screen_y))

        return int(screen_x), int(screen_y)


# Create a camera
camera = Camera3D(screen_width=800, screen_height=600, fov=60, horizon=150)

# Test data: (x, y, z, expected_screen_x, expected_screen_y)
test_data = [
    (0, 10, 0, 400, 600),  # Center, on ground, close
    (5, 10, 0, 622, 600),  # Right, on ground, close
    (-5, 10, 0, 178, 600),  # Left, on ground, close
    (0, 20, 0, 400, 375),  # Center, on ground, far
    (10, 20, 0, 622, 375),  # Right, on ground, far
    (-10, 20, 0, 178, 375),  # Left, on ground, far
    (0, 10, 10, 400, 150),  # Center, at horizon level, close
    (0, 10, 20, 400, 0),  # Center, above horizon, close
    (0, 100, 0, 400, 285),  # Center, on ground, very far
]

# Run tests
for i, (x, y, z, expected_x, expected_y) in enumerate(test_data):
    screen_x, screen_y = camera.to_2d_v2(x, y, z)
    print(f"Test {i + 1}: Input (x:{x}, y:{y}, z:{z})")
    print(f"  Expected: ({expected_x}, {expected_y})")
    print(f"  Actual:   ({screen_x}, {screen_y})")
    print(f"  {'PASS' if abs(screen_x - expected_x) <= 1 and abs(screen_y - expected_y) <= 1 else 'FAIL'}")
    print()