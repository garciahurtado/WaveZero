import utime as time

class FpsCounter():
    """
    FPS measurement using Exponential Moving Average (EMA) for stable readings.

    Uses EMA to provide smooth FPS measurements while being memory efficient.
    Lower alpha values (0.05-0.1) give smoother but slower readings,
    higher values (0.15-0.2) are more responsive but less stable.
    """

    def __init__(self):
        """Initialize FPS counter with timestamp, EMA value, and smoothing factor."""
        self.last_tick = 0    # Last recorded timestamp
        self.ema = 0          # Exponential moving average of frame times
        self.alpha = 0.008     # Smoothing factor. Lower value = smoother (0.1 = 10% weight to new samples)

    def tick(self):
        """Record frame timing and update the moving average.

        Call this once per frame to measure frame time and update the EMA.
        Should be called at the same point in each frame (start or end).
        """
        current_tick = time.ticks_ms()
        if self.last_tick != 0:
            frame_time = time.ticks_diff(current_tick, self.last_tick)
            if frame_time > 0:
                if self.ema == 0:
                    self.ema = frame_time
                else:
                    self.ema = (self.alpha * frame_time) + ((1 - self.alpha) * self.ema)

        self.last_tick = current_tick

    def fps(self):
        """Calculate current FPS from the averaged frame time.

        Returns FPS based on EMA of frame times, or 0 if no measurements yet.
        """
        return 1000 / self.ema if self.ema > 0 else 0