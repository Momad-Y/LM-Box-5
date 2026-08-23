import os
import random

import pygame

CWD = os.path.dirname(os.path.abspath(__file__))
IMAGES_DIR = f"{CWD}/resources/images"


# Jump physics, tuned for the 30 FPS loop the camera can sustain. The apex is
# JUMP_VELOCITY^2 / (2 * GRAVITY) ~= 76.5px over a ~0.6s round trip - enough
# to clear the tallest (60px) cactus with room to spare, but not enough to
# clear a low-flying pterodactyl (RUNNER_DUCK_UNDER_HEIGHT + this sprite's own
# height, ~81px). That gap is what makes ducking an actually required, not
# just cosmetic, response to the low ptero. A taller jump than this defeats
# duck entirely - see gui/gui.py's RUNNER_DUCK_UNDER_HEIGHT comment.
JUMP_VELOCITY = -19
GRAVITY = 2.1

# Frames between animation swaps at 30 FPS
RUN_ANIMATION_FRAMES = 5
PTERO_ANIMATION_FRAMES = 8

# Sprite scales. The source art is padded with transparent space (the runner
# sits in the bottom of a taller canvas, and the cacti have between 0 and 8
# blank rows underneath), so every image is trimmed to its opaque bounds
# before scaling. That keeps sprites level on the ground line and stops the
# hitboxes covering empty space above the runner's head.
RUNNER_SCALE = 2.4
CACTUS_SCALE = 1.2
PTERO_SCALE = 2.4

# Ducking squashes to this fraction of the running height. The raw crouch art
# is only ~25% shorter than the standing art, which isn't enough of a
# difference for ducking under a pterodactyl to be reliable.
DUCK_HEIGHT_RATIO = 0.55


class Runner(pygame.sprite.Sprite):
    def __init__(self, pos_x, ground_y):
        super().__init__()

        self.run_imgs = [
            _scale(_load_trimmed("runner-run-1.png"), RUNNER_SCALE),
            _scale(_load_trimmed("runner-run-2.png"), RUNNER_SCALE),
        ]

        self.jump_img = _scale(_load_trimmed("runner-jump.png"), RUNNER_SCALE)

        # Squash the crouch art so ducking actually lowers the runner's profile
        run_height = self.run_imgs[0].get_height()
        duck_height = int(run_height * DUCK_HEIGHT_RATIO)
        self.duck_imgs = []
        for name in ("runner-duck-1.png", "runner-duck-2.png"):
            duck = _load_trimmed(name)
            self.duck_imgs.append(
                _scale_to(duck, duck.get_width() * RUNNER_SCALE, duck_height)
            )

        self.run_index = 0
        self.duck_index = 0
        self.image = self.run_imgs[0]

        self.pos_x = pos_x
        self.ground_y = ground_y

        # Height above the ground line. Tracking altitude (rather than a
        # raw rect.y) keeps the sprite's feet planted on the ground no
        # matter which state image is showing, since the run/jump/duck
        # frames all have different heights.
        self.altitude = 0

        self.velocity_y = 0
        self.jumping = False
        self.ducking = False

        self.animation_timer = 0

        self.rect = self.image.get_rect()
        self._align_to_ground()

    def _align_to_ground(self):
        """Place the current image so its feet sit on the ground line."""
        self.rect = self.image.get_rect()
        self.rect.x = self.pos_x
        self.rect.bottom = self.ground_y - self.altitude

    def update(self, jump_input=False, duck_input=False, jump_sound=None, dt_scale=1.0):
        if jump_input and not self.jumping:
            self.jumping = True
            self.velocity_y = JUMP_VELOCITY  # a launch speed, not a per-frame delta - not scaled
            if jump_sound is not None:
                jump_sound.play()

        if self.jumping:
            # Semi-implicit Euler under a variable timestep: both the
            # velocity change and the position change scale by dt_scale, so
            # the jump's real-world height and duration stay the same
            # regardless of the frame rate they're integrated at.
            self.velocity_y += GRAVITY * dt_scale
            # velocity_y is negative going up, so subtracting it raises altitude
            self.altitude -= self.velocity_y * dt_scale
            self.image = self.jump_img

            if self.altitude <= 0:
                self.altitude = 0
                self.jumping = False
                self.velocity_y = 0

        elif duck_input:
            self.ducking = True
            self.animation_timer += dt_scale
            if self.animation_timer >= RUN_ANIMATION_FRAMES:
                self.duck_index = (self.duck_index + 1) % 2
                self.animation_timer = 0
            self.image = self.duck_imgs[self.duck_index]

        else:
            self.ducking = False
            self.animation_timer += dt_scale
            if self.animation_timer >= RUN_ANIMATION_FRAMES:
                self.run_index = (self.run_index + 1) % 2
                self.animation_timer = 0
            self.image = self.run_imgs[self.run_index]

        self._align_to_ground()


class Obstacle(pygame.sprite.Sprite):
    def __init__(self, image, pos_x, pos_y):
        super().__init__()
        self.image = image
        self.rect = self.image.get_rect()
        self.rect.x = pos_x
        self.rect.y = pos_y

    def update(self, game_speed, kill_x=-100, dt_scale=1.0):
        self.rect.x -= game_speed
        if self.rect.right < kill_x:
            self.kill()



# Obstacles spawn every ~1.5-3s for the whole run, but there are only 6
# cactus and 2 ptero source images - loaded and scaled once each here and
# reused for every spawn, rather than freshly from disk every time. Safe to
# share: each Obstacle gets its own `rect` (see Obstacle.__init__), and the
# shared Surface is only ever blitted, never mutated per-instance.
_cactus_image_cache = {}
_ptero_image_cache = None
_cloud_image_cache = None


def _cached_cactus_image(cactus_num):
    if cactus_num in _cactus_image_cache:
        return _cactus_image_cache[cactus_num]

    image = _scale(_load_trimmed(f"cactus-{cactus_num}.png"), CACTUS_SCALE)
    # Only memoize once a display exists: _load_trimmed silently skips
    # convert_alpha() without one (pygame.error), and caching that
    # unoptimized surface here would stick for the rest of the process
    # even after a display shows up later. Real gameplay always has a
    # display by the time any obstacle spawns, so this never costs a
    # repeated disk load in practice - it only guards a startup-order edge
    # case (e.g. constructing one for a test before any display exists).
    if pygame.display.get_surface() is not None:
        _cactus_image_cache[cactus_num] = image
    return image


def _cached_ptero_images():
    global _ptero_image_cache
    if _ptero_image_cache is not None:
        return _ptero_image_cache

    images = [
        _scale(_load_trimmed("ptero-1.png"), PTERO_SCALE),
        _scale(_load_trimmed("ptero-2.png"), PTERO_SCALE),
    ]
    # Only memoize once a display exists - see _cached_cactus_image for why.
    if pygame.display.get_surface() is not None:
        _ptero_image_cache = images
    return images


def _cached_cloud_image():
    global _cloud_image_cache
    if _cloud_image_cache is not None:
        return _cloud_image_cache

    # convert_alpha() so every blit is a fast same-format copy instead of a
    # slow per-pixel format translation - Cactus/Ptero already do this via
    # _load_trimmed, Cloud never had the equivalent.
    image = pygame.image.load(f"{IMAGES_DIR}/cloud.png")
    try:
        image = image.convert_alpha()
    except pygame.error:
        # No display yet (e.g. importing for a test); the raw surface is
        # fine - see _cached_cactus_image for why this isn't cached either.
        pass
    # Only memoize once a display exists - see _cached_cactus_image for why.
    if pygame.display.get_surface() is not None:
        _cloud_image_cache = image
    return image


class Cactus(Obstacle):
    def __init__(self, pos_x, pos_y):
        cactus_num = random.randint(1, 6)
        super().__init__(_cached_cactus_image(cactus_num), pos_x, pos_y)


class Ptero(Obstacle):
    def __init__(self, screen_width=800, height=None):
        self.images = _cached_ptero_images()

        self.index = 0
        self.animation_timer = 0
        if height is None:
            height = random.choice([200, 250, 300])
        super().__init__(self.images[0], screen_width, height)

    def update(self, game_speed, kill_x=-100, dt_scale=1.0):
        # Scaled the same way game_speed already is, so the wing-flap rate
        # stays proportional to how far the pterodactyl has actually moved
        # regardless of the frame rate driving both.
        self.animation_timer += dt_scale
        if self.animation_timer >= PTERO_ANIMATION_FRAMES:
            self.index = (self.index + 1) % 2
            # Keep the feet planted while the wing frames swap sizes
            bottom, left = self.rect.bottom, self.rect.left
            self.image = self.images[self.index]
            self.rect = self.image.get_rect()
            self.rect.bottom, self.rect.left = bottom, left
            self.animation_timer = 0

        self.rect.x -= game_speed
        if self.rect.right < kill_x:
            self.kill()


class Cloud(pygame.sprite.Sprite):
    def __init__(self, spawn_x=800, y_min=50, y_max=200):
        super().__init__()
        self.image = _cached_cloud_image()
        self.rect = self.image.get_rect()
        self.rect.x = spawn_x + random.randint(0, 100)
        self.rect.y = random.randint(y_min, max(y_min, y_max))
        self.speed = random.randint(3, 8)

    def update(self, kill_x=-100):
        self.rect.x -= self.speed
        if self.rect.right < kill_x:
            self.kill()


def _load_trimmed(name):
    """Load an image cropped to its opaque pixels.

    The source art pads each sprite with transparent space, and the amount
    differs per file. Cropping it away means a sprite's rect matches what the
    player actually sees, so bottom-aligning to the ground line works for
    every sprite and collisions don't trigger on empty space.
    """
    image = pygame.image.load(f"{IMAGES_DIR}/{name}")
    try:
        image = image.convert_alpha()
    except pygame.error:
        # No display yet (e.g. importing for a test); the raw surface is fine
        pass
    return image.subsurface(image.get_bounding_rect()).copy()


def _scale(image, factor):
    size = image.get_rect().size
    return pygame.transform.scale(image, (int(size[0] * factor), int(size[1] * factor)))


def _scale_to(image, width, height):
    return pygame.transform.scale(image, (int(width), int(height)))


def ground_line_offset(surface):
    """How far below a ground tile's top edge its solid line actually sits.

    The ground art is a band of scattered dirt specks with one dense line
    through it, and that line is not at the top of the image. Blitting the
    tile at the ground Y would therefore draw the visible ground below where
    the sprites stand, making everything look like it floats. Callers offset
    the blit by this value so the drawn line matches the sprites' feet.
    """
    alpha = pygame.surfarray.array_alpha(surface)  # indexed [x][y]
    opaque_per_row = (alpha > 0).sum(axis=0)
    return int(opaque_per_row.argmax())
