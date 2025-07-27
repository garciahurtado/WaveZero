import bisect
import math
import unittest

try:
    # For MicroPython
    from uarray import array
except ImportError:
    # For CPython
    from array import array

from profiler import timed
from scaler.const import DEBUG_SCALES, INK_RED
from print_utils import printc

class ScalePatterns:
    """
    Stores, creates and manages the scaling patters to use in upscale / downscaling (only horizontal)
    """
    horiz_patterns = None
    scale_precision = 8
    decimal_precision = 3
    valid_scales = []

    def __init__(self):
        self.create_horiz_patterns()
        if DEBUG_SCALES:
            self.print_patterns(0, len(self.horiz_patterns))

    def get_pattern(self, scale):
        patterns = self.get_horiz_patterns()
        the_pattern = patterns[scale]

        return the_pattern

    def get_horiz_patterns(self):
        """ Return exisiting, or create if it doesn't exist """
        if not self.horiz_patterns:
            self.horiz_patterns = self.create_horiz_patterns()

        return self.horiz_patterns

    def create_horiz_patterns(self):
        """
        By varying the size of the step between integer scales, we can change the number of steps and make
        the scaling process smoother or more coarse.

        steps tested = 0.016, 0.032, 0.064, 0.125, 0.250, 0.500
        * Since the patterns are only 8 elements, the step must be a multiple of 1/8, so anything under 0.125 would
        effectively become 0.125 when rendered
        """
        patterns_all = {}

        patterns1 = self.create_patterns(0, 1, step=0.125)  # 8 steps
        patterns2 = self.create_patterns(1, 4, step=0.250)  # 4 steps
        patterns3 = self.create_patterns(4, 8, step=0.500)  # 2 steps
        patterns4 = self.create_patterns(8, 16, step=1)     #

        patterns_all |= patterns1
        patterns_all |= patterns2
        patterns_all |= patterns3
        patterns_all |= patterns4

        self.horiz_patterns = patterns_all
        self.valid_scales = sorted(list(self.horiz_patterns.keys()))

        return self.horiz_patterns

    def create_patterns(self, from_scale, to_scale, step=0.125):
        pattern_list = {}
        num_scales = int((to_scale - from_scale) / step)
        to_scale = int(to_scale)

        for i in range(num_scales):
            from_scale += step
            # from_scale = round(from_scale, self.decimal_precision)
            pattern_list[from_scale] = self.create_one_pattern(from_scale)

        # The last pattern should be a whole number
        pattern_list[to_scale] = self.create_one_pattern(to_scale)

        return pattern_list

    def create_one_pattern(self, scale):
        """
        Fractional patterns are converted into lists of integers like this:
        SCALE 0.125: [0, 0, 0, 0, 1, 0, 0, 0],  # 12.5% scaling
        SCALE 2.500: [3, 2, 3, 2, 3, 2, 3, 2],  # 2.5x scaling
        """
        size = self.scale_precision # Number of elements in one pattern (ie: 8)

        if scale == int(scale):
            """ integer scales are the easiest, every element equals the current scale """
            pattern = [scale] * size
        else:
            """ We have a fractional scale, we will separate the decimal part. """
            whole_scale = int(scale)
            frac_scale = scale - whole_scale

            """ To start, fill out a basic integer pattern """
            pattern = [whole_scale] * size
            portion = 1/frac_scale      # portion of 1 that 1 frac_scale represents
            step_8 = int(portion * 8) # we scale by 8 so that we can step by it

            for i in range(0, size * 8, step_8):
                """ increase some numbers in the pattern so that the total average = scale"""
                idx = round(i/size)
                idx = idx % size
                pattern[idx] = whole_scale+1

        pattern = self.pattern_to_array(pattern)  # Convert to array
        return pattern

    def print_patterns(self, first=0, last=10):
        print()
        print(f"### PRINTING SCALING PATTERNS ({first} to {last}) ###")
        patterns = self.get_horiz_patterns()
        pattern_keys = list(patterns.keys())
        pattern_keys.sort()

        str_out = ''
        for scale in pattern_keys:
            pattern = patterns[scale]
            if first <= scale < last:
                actual = sum(pattern) / self.scale_precision
                str_out += "\n"
                str_out += f"{scale} ({actual:.03f}):\n"
                list_str = ", ".join([str(num) for num in pattern])
                str_out += f"   [{list_str}]\n"

        print(str_out)

    def find_closest_scale(self, input_scale: float) -> float:
        """
        Finds the closest valid scale to the input scale (assuming a sorted list of scales)
        using binary search (bisect module).

        The function first truncates the input to three decimal places
        before finding the closest match.
        """
        valid_scales = self.valid_scales

        # Truncate the input float to three decimal places
        truncated_input = math.trunc(input_scale * 1000) / 1000

        # Find the insertion point using bisect_left from bisect.py
        index = bisect.bisect_left(valid_scales, truncated_input)  #

        # Handle edge cases:
        if index == 0:
            return valid_scales[0]
        if index == len(valid_scales):
            return valid_scales[-1]

        # Compare with the element at valid_scales[index - 1] and valid_scales[index]
        before = valid_scales[index - 1]
        after = valid_scales[index]

        diff_before = truncated_input - before
        diff_after = after - truncated_input

        if diff_before <= diff_after:
            return before
        else:
            return after

    @staticmethod
    def pattern_to_array(pattern):
        """
        Create bytebuffer to store 1 scaling pattern of 8 elements, each 32bits (4 bytes)
        """
        arr_buff = bytearray(8 * 4)
        final_array = array('L', arr_buff)

        for i in range(8):
            final_array[i] = int(pattern[i])

        return final_array
