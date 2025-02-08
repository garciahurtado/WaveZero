import utime
from ucollections import OrderedDict
import asyncio

class Profiler():
    __slots__ = ()  # No instance attributes needed
    profile_labels = OrderedDict()
    enabled = True

    @staticmethod
    def start_profile(label):
        """Start timing a code block."""
        if not Profiler.enabled:
            return

        record = Profiler.profile_labels.get(label)
        if record is None:
            # [num_calls, start_usecs, total_time]
            record = [0, 0, 0]
            Profiler.profile_labels[label] = record

        record[1] = utime.ticks_us()

    @staticmethod
    def end_profile(label):
        """End timing a code block."""
        if not Profiler.enabled:
            return

        record = Profiler.profile_labels.get(label)
        if not record or not record[1]:
            return

        elapsed = utime.ticks_diff(utime.ticks_us(), record[1])
        record[0] += 1  # Increment call count
        record[1] = 0  # Reset start time
        record[2] += elapsed  # Add to total time

    @staticmethod
    def dump_profile(filter_str=None):
        """Dump profiling data."""
        if not Profiler.enabled:
            return

        print("\nProfile Results:")
        print(f"{'func': <32} {'runs': <8} {'avg ms': <14} {'total ms': >9}")
        print("-" * 68)

        if not Profiler.profile_labels:
            print("No profiling data available.\n")
            return

        # Pre-calculate filter matches if filter exists
        show_label = (
            (lambda l: filter_str in l) if filter_str
            else (lambda l: True)
        )

        # Sort by total time (record[2])
        for label, record in sorted(
                Profiler.profile_labels.items(),
                key=lambda x: x[1][2],
                reverse=True
        ):
            if not show_label(label):
                continue

            num_runs, _, total_time = record
            if num_runs == 0:
                print(f"{label: <32} {'N/A': <8} {'N/A': <14} {'N/A': >9}")
                continue

            avg_time_ms = (total_time / num_runs) / 1000
            total_time_ms = total_time / 1000
            print(f"{label: <32} {num_runs: <8} {avg_time_ms: <14.4f} {total_time_ms: >9.2f}")
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
