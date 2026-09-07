"""Starting the mixer, and coping when there is nothing to start it on.

pygame.mixer.init() raises when the machine has no usable audio endpoint -
a PC with no sound card, a VM, a container, a broken or in-use driver. The
app used to call it unguarded during Game.__init__, so a missing audio
device did not cost you the sound: it cost you the whole game, before a
window ever appeared. A camera game should still be playable in silence.

The awkward part is what comes after. There are ~25 places that build a
mixer.Sound and ~15 that call .play() on one, and wrapping every one of
them in "if audio is available" is precisely the kind of change that gets
24 of 25 right and crashes on the one that was missed months later.

So nothing is guarded at the call sites. When there is no device,
load_sound() hands back a SilentSound that answers the same calls and does
nothing, and every existing `.play()`, `.set_volume()` and `.stop()` keeps
working untouched.
"""
import pygame
from pygame import mixer


class SilentSound:
    """A mixer.Sound stand-in for when there is no audio device.

    Implements the parts of the Sound interface this app uses. Anything it
    is asked to do, it does not do, successfully.
    """

    def play(self, *args, **kwargs):
        return None

    def stop(self, *args, **kwargs):
        return None

    def fadeout(self, *args, **kwargs):
        return None

    def set_volume(self, *args, **kwargs):
        return None

    def get_volume(self):
        return 0.0

    def get_length(self):
        return 0.0

    def get_num_channels(self):
        return 0


def start_audio():
    """Initialise the mixer. Returns whether sound is actually available.

    A failure here is reported once and then forgotten about: the player
    gets a silent game rather than no game, and every later audio call is
    absorbed by SilentSound.
    """
    try:
        mixer.init()
    except pygame.error as error:
        print(f"NOTE: no audio device available ({error}); running without sound")
        return False
    return True
