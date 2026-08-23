import os

# Must be set before mediapipe (imported transitively by gui) loads its
# native library, otherwise its C++ backend still prints INFO/WARNING
# startup noise (EGL/GL context init, XNNPACK delegate, feedback manager)
# on every model load.
os.environ.setdefault("GLOG_minloglevel", "2")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")

from gui import Game

if __name__ == "__main__":
    game = Game()
