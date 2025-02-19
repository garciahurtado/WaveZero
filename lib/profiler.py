from typing import NamedTuple

import utime
from ucollections import OrderedDict, namedtuple
import asyncio

from fps_counter import FpsCounter

ProfileLabel = namedtuple(
    "ProfileLabel",
    (
        "start_usecs",
        "frame_calls",
        "frame_time"
        "total_calls",
        "total_time"
    ))

class ProfileLabel:
    start_usecs = 0
    frame_calls = 0
    frame_time = 0
    total_calls = 0
    total_time = 0

class Profiler:
    __slots__ = ()  # No instance attributes needed
    enabled = False
    fps: FpsCounter = None
    profile_labels = OrderedDict()

    @staticmethod
    def start_frame():
        """ Starts a new frame: reset frame level stats while keeping the totals """
        for key, record in Profiler.profile_labels.items():
            record.frame_calls = 0
            record.frame_time = 0

    @staticmethod
    def start_profile(label):
        """Start timing a code block."""
        if not Profiler.enabled:
            return

        record = Profiler.profile_labels.get(label)
        if record is None:
            record = ProfileLabel()
            Profiler.profile_labels[label] = record

        record.start_usecs = utime.ticks_us()

    @staticmethod
    def end_profile(label):
        """End timing a code block."""
        if not Profiler.enabled:
            return

        record = Profiler.profile_labels.get(label)
        if not record or not record.start_usecs:
            return

        elapsed = utime.ticks_diff(utime.ticks_us(), record.start_usecs)
        record.frame_time += elapsed  # Add to frame time
        record.total_time += elapsed  # Add to total time
        record.total_calls += 1  # Increment call count
        record.frame_calls += 1  # Increment call count
        record.start_usecs = 0  # Reset start time

    @staticmethod
    def dump_profile(filter_str=None):
        """Dump profiling data."""
        if not Profiler.enabled:
            return

        max_col = 79
        print()
        print("\nProfile Results:")
        print()
        print(f"{'func': <31} {'Calls': >6} {'Per frame': >10} {'Avg ms': >9} {'Frame ms': >9} {'Tot ms': >9} ")
        print("-" * max_col)

        if not Profiler.profile_labels:
            print("No profiling data available.\n")
            return

        # Define filter function without lambda
        if filter_str:
            def show_label(label):
                return filter_str in label
        else:
            def show_label(label):
                return True

        # Sort using attribute access instead of list index
        def sort_key(item):
            return item[1].total_time

        total_frame_time = 0 # keep running tally

        for label, record in sorted(
                Profiler.profile_labels.items(),
                key=sort_key,
                reverse=True
        ):
            if not show_label(label):
                continue

            frame_calls = record.frame_calls
            frame_time = record.frame_time / 1000 # us -> ms
            total_frame_time += frame_time

            total_calls = record.total_calls
            total_time_ms = record.total_time / 1000 # us -> ms

            if total_calls == 0:
                print(f"{label: <30} {'N/A': <8} {'N/A': <10} {'N/A': <14} {'N/A': >9} {'N/A': >9}")
                continue

            avg_time_ms = total_time_ms / total_calls
            print(f"{label: <31} {total_calls: >6} {frame_calls: >10} {avg_time_ms: >9.2f} {frame_time: >9.2f} {total_time_ms: >9.2f} ")

        print('-' * max_col)
        print(f"TOTALS: {total_frame_time:>61.2f}")

        if Profiler.fps:
            frame_time = Profiler.fps.frame_ms()

        print()


    @staticmethod
    def clear():
        """Clear all profiling data."""
        Profiler.profile_labels.clear()


def profile(func):
    """Decorator for profiling functions."""

    def wrapper(*args, **kwargs):
        if not Profiler.enabled:
            return func(*args, **kwargs)

        Profiler.start_profile(func.__name__)
        try:
            return func(*args, **kwargs)
        finally:
            Profiler.end_profile(func.__name__)

    return wrapper
