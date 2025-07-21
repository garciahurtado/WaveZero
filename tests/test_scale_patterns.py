import sys
import unittest

""" In order to install unittest, run from CMD:
>mpremote mip install unittest

Install unittest
Installing unittest (latest) from https://micropython.org/pi/v2 to /lib
Installing: /lib/unittest/__init__.mpy

In order to run the tests, run from a MP REPL:
>>> import tests.test_scale_patterns
This should output the test results
"""

# Add the project root to the Python path so it can find the 'lib' directory
sys.path.insert(0, '../lib')
from scaler.scale_patterns import ScalePatterns

class TestScalePatterns(unittest.TestCase):
    def setUp(self):
        """This method is called before each test."""
        self.scale_patterns = ScalePatterns()
        # The __init__ of ScalePatterns calls create_horiz_patterns,
        # so the valid_scales list is already populated.

    def test_find_closest_scale(self):
        """Tests the find_closest_scale method with a variety of inputs."""
        test_cases = {
            # Original cases
            0.05: 0.125, 0.1: 0.125, 0.125: 0.125, 0.187: 0.125, 0.1875: 0.125,
            0.188: 0.25, 0.3: 0.25, 0.9: 0.875, 1: 1.0, 1.0: 1.0, 1.1: 1.0,
            1.125: 1.0, 1.126: 1.25, 1.9: 2.0, 2: 2.0, 2.0: 2.0, 2.2: 2.0,
            2.25: 2.0, 2.3: 2.5, 4.7: 4.5, 4.75: 4.5, 4.8: 5.0, 5: 5.0, 5.0: 5.0,
            # Boundary cases
            0.0: 0.125,  # Smallest possible input
            5.1: 5.0,    # Input greater than max scale
            # Mid-point cases to check rounding behavior
            2.125: 2.0,  # Exactly between 2.0 and 2.25
            4.75: 4.5,   # Exactly between 4.5 and 5.0
        }

        for test_input, expected_output in test_cases.items():
            with self.subTest(test_input=test_input):
                actual_output = self.scale_patterns.find_closest_scale(test_input)
                self.assertEqual(actual_output, expected_output,
                                 f"Failed for input {test_input}: expected {expected_output}, got {actual_output}")

# Calling unittest.main() directly will run the tests when this file is imported.
unittest.main()