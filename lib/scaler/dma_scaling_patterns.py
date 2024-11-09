from array import array
from uctypes import addressof
from utils import aligned_buffer

class ScalingPatterns:
    """Manages DMA scaling patterns for the DMA sprite scaler"""

    def __init__(self, debug=False):
        self.debug = debug
        self.pattern_size = 8  # num elements in one pattern

        # Initialize pattern arrays
        self.h_patterns_ptr = None
        self.v_patterns_up_ptr = None
        self.v_patterns_down_ptr = None

        # Keep references to prevent GC
        self.all_h_patterns = []
        self.all_v_patterns = []

        self.all_patterns = []  # Store both buffers and arrays!
        self.all_buffers = []

        # Create all patterns
        self._init_patterns()

    def _init_patterns(self):
        """
        Scaling Patterns ----------------------------------

        Initialize all scaling patterns and their aligned buffers
        These buffers will be used to double horizontal pixels at set intervals, in order to implement upscaling
        The data will be sent to the pixel_out DMA count field. from another channel with a ring buffer of
        size = len(pattern)
        """
        # Define base patterns
        self.h_patterns_int = [
            [2, 2, 1, 1, 1, 1, 1, 1],  # 100%
            [1, 1, 1, 1, 2, 1, 1, 1],  # 112.5%
            [1, 1, 2, 1, 1, 1, 2, 1],  # 125%
            [1, 1, 2, 1, 1, 2, 1, 2],  # 137.5%
            [1, 2, 1, 2, 1, 2, 1, 2],  # 150%
            [2, 1, 2, 2, 1, 2, 1, 2],  # 162.5%
            [2, 1, 2, 2, 2, 1, 2, 2],  # 175%
            [2, 2, 2, 2, 1, 2, 2, 2],  # 187.5%
            [2, 2, 2, 2, 2, 2, 2, 2],  # 200%
        ]

        self.v_patterns_down_int = [
            [1, 1, 1, 1, 1, 1, 1, 1],
            [0, 0, 0, 0, 1, 0, 0, 0],  # 12.5%
            [0, 0, 1, 0, 0, 0, 1, 0],  # 25%
            [0, 0, 1, 0, 0, 1, 0, 1],  # 37.5%
            [0, 1, 0, 1, 0, 1, 0, 1],  # 50%
            [1, 0, 1, 1, 0, 1, 0, 1],  # 62.5%
            [1, 0, 1, 1, 1, 0, 1, 1],  # 75%
            [1, 1, 1, 1, 0, 1, 1, 1],  # 87.5%
            [1, 1, 1, 1, 1, 1, 1, 1],  # 100%
        ]

        self.v_patterns_up_int = [
            [1, 1, 1, 1, 1, 1, 1, 1],  # 100%
            [1, 1, 1, 1, 2, 1, 1, 1],  # 112.5%
            [1, 1, 2, 1, 1, 1, 2, 1],  # 125%
            [1, 1, 2, 1, 1, 2, 1, 2],  # 137.5%
            [1, 2, 1, 2, 1, 2, 1, 2],  # 150%
            [2, 1, 2, 2, 1, 2, 1, 2],  # 162.5%
            [2, 1, 2, 2, 2, 1, 2, 2],  # 175%
            [2, 2, 2, 2, 1, 2, 2, 2],  # 187.5%
            [2, 2, 2, 2, 2, 2, 2, 2],  # 200%
        ]

        # Create pointer arrays
        # self.h_patterns_ptr = array('L', [0x00000000] * len(self.h_patterns_int))
        self.v_patterns_down_ptr = array('L', [0x00000000] * len(self.v_patterns_down_int))
        self.v_patterns_up_ptr = array('L', [0x00000000] * len(self.v_patterns_up_int))

        # Create aligned array for pattern pointers
        ptr_buf = aligned_buffer(len(self.h_patterns_int) * 4, alignment=32)
        self.h_patterns_ptr = array('L', ptr_buf)

        # Initialize horizontal patterns
        for i, scale_pattern in enumerate(self.h_patterns_int):
            # Create aligned pattern buffer
            h_pattern_buf = aligned_buffer(8 * 4, alignment=32)
            h_pattern = array('L', h_pattern_buf)

            pattern_addr = addressof(h_pattern)
            if self.debug:
                print(f"Pattern {i}:")
                print(f"  Buffer addr: 0x{pattern_addr:08x}")
                print(f"  Alignment: {pattern_addr % 32}")

            # Fill pattern data
            for j, element in enumerate(scale_pattern):
                h_pattern[j] = int(element)

            # Store aligned pointer
            self.h_patterns_ptr[i] = pattern_addr
            self.all_h_patterns.append(h_pattern)
            self.all_buffers.append(h_pattern_buf)

        # Initialize horizontal patterns
        for i, scale_pattern in enumerate(self.h_patterns_int):
            h_pattern_buf = aligned_buffer(8 * 4, alignment=32)
            h_pattern = array('L', h_pattern_buf)

            self.all_buffers.append(h_pattern_buf)  # Keep buffer reference
            self.all_patterns.append(h_pattern)  # Keep array reference

            pattern_addr = addressof(h_pattern)
            if self.debug:
                print(f"Pattern {i} address: 0x{pattern_addr:08x}")
                print(f"Alignment check: {pattern_addr % 32}/32")
                print(f"Pattern buffer address: 0x{addressof(h_pattern):08x}")
                print(f"Buffer alignment: {addressof(h_pattern) % 32}")

            # Fill pattern data
            for j, element in enumerate(scale_pattern):
                h_pattern[j] = int(element)
                if self.debug:
                    print(f"Element {j} at 0x{addressof(h_pattern) + (j * 4):08x}: {element}")

            self.h_patterns_ptr[i] = addressof(h_pattern)
            self.all_h_patterns.append(h_pattern)


        # Initialize vertical patterns exactly as working version
        for i, pattern in enumerate(self.v_patterns_down_int):
            v_pattern_buf = aligned_buffer(8 * 4, alignment=32)
            v_pattern = array('L', v_pattern_buf)

            self.all_buffers.append(v_pattern_buf)
            self.all_patterns.append(v_pattern)

            for j, value in enumerate(pattern):
                v_pattern[j] = int(value)

            self.v_patterns_down_ptr[i] = addressof(v_pattern)
            self.all_v_patterns.append(v_pattern)

        for i, pattern in enumerate(self.v_patterns_up_int):
            v_pattern_buf = aligned_buffer(8 * 4, alignment=32)
            v_pattern = array('L', v_pattern_buf)

            self.all_buffers.append(v_pattern_buf)
            self.all_patterns.append(v_pattern)

            for j, value in enumerate(pattern):
                v_pattern[j] = int(value)

            self.v_patterns_up_ptr[i] = addressof(v_pattern)
            self.all_v_patterns.append(v_pattern)

    def get_scale_factor(self, pattern_idx):
        """Calculate effective scale factor for a pattern"""
        if pattern_idx >= len(self.h_patterns_int):
            return 1.0
        pattern = self.h_patterns_int[pattern_idx]
        return sum(pattern) / self.pattern_size

    def get_next_pattern_index(self, current_idx, direction=1, max_idx=None):
        """Get next pattern index with bounds checking"""
        if max_idx is None:
            max_idx = len(self.h_patterns_int) - 1

        next_idx = current_idx + direction
        if next_idx > max_idx:
            return max_idx
        if next_idx < 1:
            return 1
        return next_idx

    def _create_pattern_buffer(self, pattern_data):
        """Create 32-byte aligned buffer for 8 x 32-bit pattern elements"""
        # Allocate buffer with extra space for alignment
        buffer_size = (self.pattern_size * 4) + 32  # Add 32 bytes for alignment
        raw_buf = bytearray(buffer_size)

        # Get base address and calculate alignment padding
        base_addr = addressof(raw_buf)
        align_offset = (32 - (base_addr % 32)) % 32
        aligned_addr = base_addr + align_offset

        # Create array starting at aligned address
        pattern = array('L', raw_buf[align_offset:align_offset + self.pattern_size * 4])

        # Fill pattern data
        for i, value in enumerate(pattern_data):
            pattern[i] = value

        if self.debug:
            print(f"Pattern buffer:")
            print(f"  Base addr: 0x{base_addr:08x}")
            print(f"  Aligned addr: 0x{aligned_addr:08x}")
            print(f"  Size: {len(pattern)} words")
            print(f"  Alignment: {aligned_addr % 32}")

        return pattern, raw_buf

    def validate_pattern_config(self, pattern_idx, channel):
        """Verify pattern and DMA configuration"""
        pattern_addr = self.h_patterns_ptr[pattern_idx]
        ring_size = 1 << (channel.ctrl >> 19 & 0xf)  # Extract ring_size

        print(f"Pattern Configuration:")
        print(f"  Pattern addr: 0x{pattern_addr:08x}")
        print(f"  Alignment: {pattern_addr % 32} bytes")
        print(f"  Ring size: {ring_size} bytes")
        print(f"  Pattern size: {self.pattern_size} words ({self.pattern_size * 4} bytes)")

        if pattern_addr % 32 != 0:
            raise RuntimeError("Pattern buffer not 32-byte aligned")

        if ring_size != self.pattern_size * 4:
            raise RuntimeError(f"Ring buffer size {ring_size} does not match pattern size {self.pattern_size * 4}")

    def debug_pattern_memory(self, pattern_idx):
        """Dump pattern memory contents"""
        pattern_addr = self.h_patterns_ptr[pattern_idx]
        pattern = self.all_h_patterns[pattern_idx]

        print(f"\nPattern {pattern_idx} Memory Dump:")
        print(f"Base addr: 0x{pattern_addr:08x}")

        for i in range(self.pattern_size):
            addr = pattern_addr + (i * 4)
            value = pattern[i]
            print(f"0x{addr:08x}: {value:08x}")