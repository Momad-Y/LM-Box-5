"""A frame limiter that actually honours the frame rate it is given.

pygame's own Clock.tick(fps) computes its target frame time in whole
milliseconds - `(int)((1.0 / 60) * 1000)` is **16**, not 16.67 - so
`tick(60)` really paces the loop at up to 1000/16 = 62.5 FPS. That is not a
rounding artefact of the FPS readout; the loop genuinely runs fast. It is
why the counter was seen sitting at 61-62 on screens light enough to reach
the cap. `tick_busy_loop(60)` is no better: it hits the same wrong target
more precisely (measured at exactly 62.50 FPS on this project's hardware).

This is a drop-in replacement for the parts of pygame.time.Clock the app
uses - `tick(framerate)` returning milliseconds elapsed, and `get_fps()` -
so every existing `clock.tick(60)` call site keeps working unchanged, and
60 means 60.
"""
import time
from collections import deque

# How many recent frames get_fps() averages over. Matches the window
# pygame's own Clock.get_fps() uses, so the on-screen counter stays as
# steady as it was rather than twitching on every frame.
FPS_SAMPLE_FRAMES = 10

# Sleep this far short of the deadline, then spin for the remainder.
# time.sleep() can only be trusted to wake up "no earlier than" its
# argument, and on a loaded machine it routinely overshoots by a fraction
# of a millisecond - enough to turn a 60 FPS cap into 57-58. Sleeping to
# just before the deadline and busy-waiting the last sliver keeps the cap
# accurate while leaving the CPU idle for essentially the whole frame. The
# spin only ever runs on screens light enough to reach the cap; a loop
# already missing the deadline (every camera-driven game screen on this
# hardware) never enters it at all.
SPIN_MARGIN_SECONDS = 0.0012


class FrameClock:
    """Paces a loop to a frame rate and measures the rate actually achieved."""

    def __init__(self, max_fps=None):
        """`max_fps` is a ceiling no tick() call can be talked out of.

        The app has ~23 separate `clock.tick(60)` call sites; relying on
        every one of them to keep passing the right literal forever is
        exactly how a cap quietly stops being a cap. Holding the ceiling on
        the clock itself makes "never faster than this" a property of the
        object rather than of 23 call sites agreeing.
        """
        now = time.perf_counter()
        self._max_fps = max_fps
        self._last_tick = now
        self._next_frame_at = None
        self._recent = deque(maxlen=FPS_SAMPLE_FRAMES)
        self._elapsed = 0.0
        self._raw_elapsed = 0.0

    def tick(self, framerate=0):
        """Wait as needed to keep the loop at or under `framerate`.

        Returns the milliseconds the last frame took, like pygame's Clock
        does, so callers computing `dt = clock.tick(60) / 1000` are
        unaffected. A framerate of 0 means "no request of my own" - which
        still honours the clock's own ceiling, if it has one.
        """
        entered_at = time.perf_counter()
        # The frame's own work, before any waiting this call does - which
        # is exactly what get_rawtime() reports.
        self._raw_elapsed = entered_at - self._last_tick

        framerate = self._capped(framerate)
        if framerate > 0:
            frame_seconds = 1.0 / framerate

            if self._next_frame_at is None:
                self._next_frame_at = entered_at + frame_seconds
            else:
                self._sleep_until(self._next_frame_at)
                # Advance from the deadline rather than from now, so a
                # frame that wakes a hair late doesn't push every later
                # frame later still (which would drift the cap downward).
                self._next_frame_at += frame_seconds
                # ...but if the loop is genuinely slower than the cap,
                # resync instead of accumulating a debt it would later
                # "repay" as a burst of zero-length frames.
                if self._next_frame_at <= time.perf_counter():
                    self._next_frame_at = time.perf_counter() + frame_seconds

        now = time.perf_counter()
        self._elapsed = now - self._last_tick
        self._last_tick = now
        self._recent.append(self._elapsed)
        return self._elapsed * 1000.0

    def tick_busy_loop(self, framerate=0):
        """pygame's busy-wait variant of tick().

        Present for interface parity. This clock already sleeps to just
        short of the deadline and spins the remainder, so it needs no
        separate busy-wait path - and pygame's own tick_busy_loop is not a
        finer-grained tick anyway, it just hits the same whole-millisecond
        target more precisely (see the module docstring).
        """
        return self.tick(framerate)

    def get_time(self):
        """Milliseconds the last completed frame took, waiting included.

        Same contract as pygame's Clock.get_time() - the value the previous
        tick() returned. The Credits scroll advances by this, so it has to
        keep meaning "real time since the previous frame".
        """
        return self._elapsed * 1000.0

    def get_rawtime(self):
        """Milliseconds the last frame spent working, waiting excluded."""
        return self._raw_elapsed * 1000.0

    def _capped(self, framerate):
        """The rate to actually pace at: the caller's, but never above the
        clock's own ceiling."""
        if not self._max_fps:
            return framerate
        if framerate <= 0:
            return self._max_fps
        return min(framerate, self._max_fps)

    @staticmethod
    def _sleep_until(deadline):
        remaining = deadline - time.perf_counter()
        if remaining <= 0:
            return
        if remaining > SPIN_MARGIN_SECONDS:
            time.sleep(remaining - SPIN_MARGIN_SECONDS)
        while time.perf_counter() < deadline:
            pass

    def get_fps(self):
        """The rate over the last FPS_SAMPLE_FRAMES frames, 0 before any."""
        if not self._recent:
            return 0.0
        average = sum(self._recent) / len(self._recent)
        if average <= 0:
            return 0.0
        return 1.0 / average
