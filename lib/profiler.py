from typing import NamedTuple
from ucollections import OrderedDict
import time

from fps_counter import FpsCounter
from scaler.const import DEBUG_PROFILER, INK_YELLOW, DEBUG_FRAME_ID
from scaler.scaler_debugger import printc


class ProfileRecord:
    """Holds all profiling data for a single labeled function."""
    __slots__ = ('call_stack', 'frame_calls', 'frame_time', 'total_calls', 'total_time', 'ema_frame_us')

    def __init__(self):
        self.call_stack = []
        self.frame_calls = 0
        self.frame_time = 0
        self.total_calls = 0
        self.total_time = 0
        self.ema_frame_us = 0.0


class Profiler:
    """A static class (Singleton) for lightweight, real-time function profiling."""
    __slots__ = ()      # Optimize for memory and performance by preventing instance attributes.
    enabled = True if DEBUG_PROFILER else False
    fps: FpsCounter = None
    profile_labels = OrderedDict()
    frame_started = False
    ema_alpha = 0.03
    frame_id = 0

    @staticmethod
    def start_frame():
        """Starts a new frame. Must be called once per frame before any profiling.

        Calculates the EMA for the previous frame's data then resets per-frame stats.
        """
        if Profiler.frame_started:
            for key, record in Profiler.profile_labels.items():
                # Update the EMA with the total time this function took in the completed frame.
                if record.ema_frame_us == 0:
                    record.ema_frame_us = float(record.frame_time)
                else:
                    alpha = Profiler.ema_alpha
                    record.ema_frame_us = (alpha * record.frame_time) + ((1 - alpha) * record.ema_frame_us)

                # Reset per-frame stats for the new frame.
                record.frame_calls = 0
                record.frame_time = 0
        else:
            # First frame has no prior data to process.
            Profiler.frame_started = True

        Profiler.frame_id += 1

    @staticmethod
    def start_profile(label):
        """Start timing a code block."""
        if not Profiler.enabled:
            return

        record = Profiler.profile_labels.get(label)
        if record is None:
            record = ProfileRecord()
            Profiler.profile_labels[label] = record

        record.call_stack.append(time.ticks_us())

    @staticmethod
    def end_profile(label):
        """End timing a code block."""
        if not Profiler.enabled:
            return

        now = time.ticks_us()
        record = Profiler.profile_labels.get(label)
        if not record or not record.call_stack:
            return

        start_time = record.call_stack.pop()
        elapsed = time.ticks_diff(now, start_time)
        record.frame_time += elapsed
        record.total_time += elapsed
        record.total_calls += 1
        record.frame_calls += 1

    @staticmethod
    def dump_profile(filter_str=None):
        """Dump profiling data."""
        if not Profiler.enabled:
            return

        max_col = 76
        print()
        print(f"\nProfile Results")
        print(f"FRAME #{Profiler.frame_id:,}")

        print()
        printc(f"{'function': <28} {'Calls/Frame': >11} {'EMA Avg ms': >11} {'Avg Call ms': >13} {'Total ms': >9}", INK_YELLOW)
        printc("-" * max_col, INK_YELLOW)

        if not Profiler.profile_labels:
            printc("No profiling data available.\n")
            return

        # Create a list of records to sort by the calculated EMA Frame ms
        profile_data = []
        for label, record in Profiler.profile_labels.items():
            if filter_str and filter_str not in label:
                continue

            if record.total_calls > 0:
                # Use the stable EMA of the function's total time per frame.
                ema_frame_ms = record.ema_frame_us / 1000
                profile_data.append((label, record, ema_frame_ms))

        # Sort by the smoothed frame time to show the most impactful functions first.
        profile_data.sort(key=lambda item: item[2], reverse=True)

        for label, record, ema_frame_ms in profile_data:
            total_time_ms = record.total_time / 1000
            # Calculate the average per-call EMA for display.
            ema_avg_ms = (record.ema_frame_us / record.frame_calls) / 1000 if record.frame_calls > 0 else 0
            # Calculate the lifetime average call time.
            avg_call_ms = (record.total_time / record.total_calls) / 1000
            print(f"{label: <28} {record.frame_calls: >11} {ema_avg_ms: >11,.3f} {avg_call_ms: >13,.3f} {int(total_time_ms): >9,}")

        printc('-' * max_col, INK_YELLOW)
        total_frame_time = sum(r.frame_time for r in Profiler.profile_labels.values()) / 1000
        printc(f"PROFILED FRAME TIME: {total_frame_time:53,.2f}ms", INK_YELLOW)
        printc('-' * max_col, INK_YELLOW)

        if Profiler.fps:
            frame_time = Profiler.fps.frame_ms()

        print()

    @staticmethod
    def clear():
        """Clear all profiling data and reset the frame counter."""
        Profiler.profile_labels.clear()
        Profiler.frame_id = 0
        Profiler.frame_started = False

_profiler = Profiler()

def timed(func):
    """A decorator for profiling a single function call."""

    def wrapper(*args, **kwargs):
        if not _profiler.enabled:
            return func(*args, **kwargs)

        func_name = func.__name__
        _profiler.start_profile(func_name)
        try:
            result = func(*args, **kwargs)
        finally:
            _profiler.end_profile(func_name)
        return result

    return wrapper

def start_frame():
    """Starts a new frame. Must be called once per frame before any profiling.

    Calculates the EMA for the previous frame's data then resets per-frame stats.
    """
    if Profiler.frame_started:
        for key, record in Profiler.profile_labels.items():
            # Update the EMA with the total time this function took in the completed frame.
            if record.ema_frame_us == 0:
                record.ema_frame_us = float(record.frame_time)
            else:
                alpha = Profiler.ema_alpha
                record.ema_frame_us = (alpha * record.frame_time) + ((1 - alpha) * record.ema_frame_us)

            # Reset per-frame stats for the new frame.
            record.frame_calls = 0
            record.frame_time = 0
    else:
        # First frame has no prior data to process.
        Profiler.frame_started = True

    Profiler.frame_id += 1
