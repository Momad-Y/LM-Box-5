"""Every asset path the app loads must actually exist on disk.

Renaming or reorganising art and audio is easy to get 95% right: the code
is updated in most places, the files are renamed, everything looks fine -
and one reference is left pointing at a name that no longer exists. Nothing
catches it until someone opens the screen that loads it, because
`mixer.music.load()` and `pygame.image.load()` only raise at the moment
they run.

That is not hypothetical. A sound-asset rename left
`runner-bg-music.ogg` referenced by `init_runner_game` after the file had
been deleted, which crashed Runner on entry while the other two games and
the whole test suite carried on passing.

This walks the runtime source, extracts every asset path it loads, and
checks the file is there - so a half-finished rename fails here instead of
in front of a player.
"""
import pathlib
import re

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

# Only the packages that actually load assets at runtime. Tests reference
# paths of their own (including ones asserted NOT to exist), so scanning
# them here would be self-defeating.
SOURCE_DIRS = ("gui", "models")

ASSET_EXTENSIONS = ("png", "jpg", "jpeg", "ogg", "wav", "mp3", "ttf", "otf")

ASSET_REFERENCE = re.compile(
    r"""["']([^"']*resources/[^"']*\.(?:%s))["']""" % "|".join(ASSET_EXTENSIONS)
)

# Sounds are not named by path any more. load_sound() and play_music() take
# a bare filename and join it to the sounds directory themselves, so the
# full path never appears in the source for the pattern above to find.
# Without this second pattern every sound in the game silently stopped
# being checked - which is exactly what happened when load_sound() was
# introduced, and what the "are any references found at all" test below
# caught.
SOUND_REFERENCE = re.compile(
    r"""(?:load_sound|play_music)\(\s*["']([^"']+\.(?:%s))["']""" % "|".join(ASSET_EXTENSIONS)
)
SOUNDS_DIR = REPO_ROOT / "gui" / "resources" / "sounds"


def _asset_references():
    """(path_on_disk, source_location) for every asset the source loads."""
    for source_dir in SOURCE_DIRS:
        for source_file in sorted((REPO_ROOT / source_dir).rglob("*.py")):
            text = source_file.read_text()

            def where(match):
                line = text[: match.start()].count("\n") + 1
                return f"{source_file.relative_to(REPO_ROOT)}:{line}"

            for match in ASSET_REFERENCE.finditer(text):
                reference = match.group(1)
                # These are f-strings built on each module's own CWD, which
                # every module defines as the directory it lives in.
                resolved = reference.replace("{CWD}/", "")
                relative_to = source_file.parent if "{CWD}" in reference else REPO_ROOT
                yield ((relative_to / resolved), where(match))

            for match in SOUND_REFERENCE.finditer(text):
                yield ((SOUNDS_DIR / match.group(1)), where(match))


def test_some_asset_references_are_actually_found():
    # Guards the guard: if the regex or the layout ever changes so that
    # nothing matches, every other assertion here would pass vacuously.
    assert len(list(_asset_references())) > 20


def test_every_referenced_asset_exists_on_disk():
    missing = [
        f"{location} -> {path.relative_to(REPO_ROOT)}"
        for path, location in _asset_references()
        if not path.is_file()
    ]
    assert not missing, "asset(s) referenced by the code but missing:\n" + "\n".join(
        sorted(missing)
    )


def test_every_game_has_its_background_music_track():
    # Each game loads its own `<name>-bg-music.ogg`, and a missing one only
    # surfaces when that game is opened - the exact failure that motivated
    # this file.
    sounds = REPO_ROOT / "gui" / "resources" / "sounds"
    for track in ("bg-music.ogg", "balloon-bg-music.ogg", "pong-bg-music.ogg", "runner-bg-music.ogg"):
        assert (sounds / track).is_file(), f"missing background music: {track}"


def _readme_images():
    """Every local image the README shows, in either syntax it uses.

    Markdown ![](./x.png) *and* HTML <img src="./x.png">, because the README
    uses both - the side-by-side screenshot tables need real HTML. Matching
    only the markdown form would have made the check below pass while
    verifying nothing at all, which is the same trap the sound files fell
    into when they stopped being written as literal paths.
    """
    import re

    readme = (REPO_ROOT / "README.md").read_text()
    markdown = re.findall(r"!\[[^\]]*\]\((\./[^)\s]+)\)", readme)
    html = re.findall(r"""<img[^>]+src=["'](\./[^"']+)["']""", readme)
    return [link.lstrip("./") for link in markdown + html]


def test_the_readme_actually_shows_some_images():
    # Guards the guard: if the README's markup changes shape again, this
    # fails loudly instead of the check below passing on an empty list.
    assert len(_readme_images()) >= 8


def test_every_image_the_readme_links_to_exists():
    # Screenshots live outside gui/resources and are referenced only by the
    # README, so nothing else in the suite notices when they are renamed -
    # which happened, leaving six dead image links and two failing tests
    # that had been reading a screenshot as a fixture.
    missing = [link for link in _readme_images() if not (REPO_ROOT / link).is_file()]
    assert not missing, "README shows images that do not exist:\n" + "\n".join(missing)
