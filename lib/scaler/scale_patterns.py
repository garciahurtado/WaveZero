import bisect
import math

from uarray import array

from scaler.const import DEBUG_SCALES, INK_RED
from scaler.scaler_debugger import printc


class ScalePatterns:
    """
    Stores, creates and manages the scaling patters to use in upscale / downscaling (only horizontal)
    """
    horiz_patterns = None
    scale_precision = 8
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
        steps tested = 0.016, 0.032, 0.064, 0.125, 0.250, 0.500
        """
        patterns_all = {}

        patterns1 = self.create_patterns(0, 1, step=0.125) # 8 steps
        patterns2 = self.create_patterns(1, 2, step=0.250) # 8 steps
        patterns3 = self.create_patterns(2, 6, step=0.500) # 8 steps
        patterns4 = self.create_patterns(6, 14, step=1)    # 8 steps
        patterns5 = self.create_patterns(14, 18, step=1)   # 4 steps

        patterns_all |= patterns1
        patterns_all |= patterns2
        patterns_all |= patterns3
        patterns_all |= patterns4
        patterns_all |= patterns5
        # patterns_all = self.create_patterns(1, 16, step=0.5)

        self.horiz_patterns = patterns_all
        self.valid_scales = sorted(list(self.horiz_patterns.keys()))

        # self.test_find_closest()

        return self.horiz_patterns


    def create_patterns(self, from_scale, to_scale, step=0.125):
        pattern_list = {}
        num_scales = int((to_scale - from_scale) / step)

        for i in range(num_scales):
            from_scale += step
            pattern = self.create_one_pattern(from_scale)
            pattern_list[from_scale] = pattern

        return pattern_list

    def create_one_pattern(self, scale):
        """
        Fractional patterns are converted into lists of integers like this:
        SCALE 0.125: [0, 0, 0, 0, 1, 0, 0, 0],  # 12.5% scaling
        SCALE 2.500: [3, 2, 3, 2, 3, 2, 3, 2],  # 2.5x scaling
        """
        size = self.scale_precision

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

        # Find the insertion point using bisect_left from your bisect.py
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

    def test_find_closest(self):
        # TESTING -----

        test_inputs = [
            0.05, 0.1, 0.125, 0.187, 0.1875, 0.188, 0.3, 0.9,
            1, 1.0, 1.1, 1.125, 1.126, 1.9,
            2, 2.0, 2.2, 2.25, 2.3,
            4.7, 4.75, 4.8, 5, 5.0
        ]
        expected_results = {
            0.05: 0.125, 0.1: 0.125, 0.125: 0.125, 0.187: 0.125, 0.1875: 0.125,
            0.188: 0.25, 0.3: 0.25, 0.9: 0.875, 1: 1.0, 1.0: 1.0, 1.1: 1.0,
            1.125: 1.0, 1.126: 1.25, 1.9: 2.0, 2: 2.0, 2.0: 2.0, 2.2: 2.0,
            2.25: 2.0, 2.3: 2.5, 4.7: 4.5, 4.75: 4.5, 4.8: 5.0, 5: 5.0, 5.0: 5.0
        }

        results_table = []
        results_table.append(
            "| Input Scale | Truncated Input (in func) | Expected Result | Actual Python Output | Match? | Notes |")
        results_table.append(
            "| :---------- | :------------------------ | :-------------- | :------------------- | :----- | :---- |")

        all_match = True

        for test_input in test_inputs:
            actual_output = self.find_closest_scale(test_input)
            expected_output = expected_results[test_input]
            truncated_inside_func = math.trunc(test_input * 1000) / 1000
            match_status = "Yes" if actual_output == expected_output else "NO"
            notes = ""
            if actual_output != expected_output:
                all_match = False
                notes = f"Expected {expected_output}, Got {actual_output}"
            results_table.append(
                f"| {test_input:<11.4f} | {truncated_inside_func:<25.3f} | {expected_output:<15.3f} | {actual_output:<20.3f} | {match_status:<6} | {notes} |")

        print("\nTest Results for find_closest_scale:\n")
        for row in results_table:
            print(row)

        if all_match:
            print("\nAll test cases match the expected results based on the code's logic.")
        else:
            print("\nSome test cases FAILED. Please review the table above.")

