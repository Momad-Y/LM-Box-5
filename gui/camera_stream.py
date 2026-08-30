"""A non-blocking wrapper around cv2.VideoCapture.

cap.read() is a blocking call - every game loop used to stall on it every
single frame, tying the app's whole frame rate to how fast the camera
itself can deliver frames rather than how fast the app can actually run.
This runs the real, blocking reads in a background thread and hands back
whatever frame is currently available instead of waiting for a new one -
the standard fix for exactly this problem (the "increasing webcam FPS"
pattern popularized by PyImageSearch's WebcamVideoStream). See
docs/PERFORMANCE_AUDIT.md for the measurements that led here.
"""
import threading
import time

# Every live instance, so a test suite (which can construct Game()/cameras
# through many different patterns - a shared fixture, a direct patch, a
# one-off script) has one place to find and stop every background thread
# still running, rather than relying on each construction path remembering
# to tear its own down. The real app never needs this: it has exactly one
# camera for its whole lifetime, released through Game.quit_app(). See
# stop_all() and tests/conftest.py's autouse cleanup fixture.
_all_instances = []
_registry_lock = threading.Lock()


def stop_all(timeout=2.0):
    """Release every still-tracked ThreadedCapture instance.

    A safety net for test suites specifically: orphaned background
    threads (from a Game()/camera that was never explicitly torn down)
    were measured to make a 150+-test suite's process take far longer to
    actually exit than pytest's own reported test time, even though each
    individual thread is harmless in isolation - many threads periodically
    waking up adds real scheduler/GIL contention to whatever cleanup the
    interpreter does at shutdown.
    """
    with _registry_lock:
        instances = list(_all_instances)
    for instance in instances:
        instance.release(timeout=timeout)


class ThreadedCapture:
    """Drop-in replacement for cv2.VideoCapture's read()/isOpened()/
    set()/get()/release() - callers don't need to know reading happens on
    a background thread. A lock protects only the frame handoff itself,
    never the real (blocking) camera read, so a caller's .read() is never
    stuck waiting on the camera the way the raw stream's was.
    """

    def __init__(self, stream):
        self.stream = stream
        self._lock = threading.Lock()
        self._grabbed = False
        self._frame = None
        self._stopped = False
        with _registry_lock:
            _all_instances.append(self)
        # Daemon: if release() ever can't stop this thread cleanly (see
        # its docstring), the interpreter must still be able to exit
        # rather than hang on a thread stuck inside a real camera read.
        self._thread = threading.Thread(target=self._update, daemon=True)
        self._thread.start()

    def _update(self):
        while not self._stopped:
            if not self.stream.isOpened():
                # Nothing to read yet (camera never opened - e.g. no
                # hardware in a headless/test environment, or still
                # negotiating). Back off instead of busy-looping a CPU
                # core on repeated instant failures.
                time.sleep(0.05)
                continue
            try:
                # The actual blocking call - deliberately outside the
                # lock, so a caller's read() is never waiting on this.
                grabbed, frame = self.stream.read()
            except Exception:
                # A malformed/misbehaving stream (a real driver error, or
                # a test double that doesn't return a proper (bool, array)
                # pair) must not silently kill this thread forever - the
                # caller would then just see the same stale frame with no
                # error and no way to know reading ever stopped working.
                time.sleep(0.05)
                continue
            with self._lock:
                self._grabbed, self._frame = grabbed, frame
            # A real camera naturally paces this loop through its own I/O
            # latency, but nothing here can assume the wrapped stream
            # always does - a fake/mock capture (as tests substitute in
            # place of real hardware) can return instantly with no real
            # wait at all, which would otherwise spin this loop as fast
            # as the CPU allows, one such thread per Game() constructed.
            # Capping the poll rate protects against that unconditionally,
            # not just for camera streams that happen to self-throttle -
            # polling faster than this buys nothing anyway, since no
            # caller reads more than once per rendered frame.
            time.sleep(1 / 120)

    def read(self):
        """Return the most recently captured frame - never blocks."""
        with self._lock:
            return self._grabbed, self._frame

    def isOpened(self):
        return self.stream.isOpened()

    def set(self, prop_id, value):
        return self.stream.set(prop_id, value)

    def get(self, prop_id):
        return self.stream.get(prop_id)

    def release(self, timeout=2.0):
        """Stop the background thread, then release the real camera.

        Ordered specifically to never call the underlying stream's own
        release() while the background thread might still be inside a
        real, blocking .read() on that same stream - concurrent access
        right at camera teardown is exactly the kind of interaction that
        was severe enough to freeze this app's actual target hardware
        once already (see docs/PERFORMANCE_AUDIT.md's incident note).

        cv2.VideoCapture.read() doesn't poll a stop flag mid-call, so the
        background thread only notices it should stop once its current
        read returns - normally a few ms, but this hardware has already
        demonstrated a read can occasionally block far longer than that.
        If the thread doesn't stop within the timeout, the underlying
        stream is deliberately left un-released rather than risking a
        release() racing a read() already in flight - the daemon thread
        still lets the process exit either way, and the OS reclaims the
        file descriptor on process death the same way it always did
        before this class existed. A timeout here is a real, if rare,
        regression back to that old behavior, not a fully solved case -
        worth watching for in practice, not something to treat as
        theoretical.
        """
        self._stopped = True
        self._thread.join(timeout=timeout)
        if not self._thread.is_alive():
            self.stream.release()
        with _registry_lock:
            if self in _all_instances:
                _all_instances.remove(self)
