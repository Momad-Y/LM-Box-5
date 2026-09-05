# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build for LM Box 5.

One spec, three platforms. PyInstaller itself does not cross-compile -
it bundles the interpreter and native libraries of the machine it runs on -
but that only forces a separate *machine* for macOS:

- Windows can be built from Linux after all, by running a real Windows
  Python under Wine in a container rather than cross-compiling at all.
  See scripts/build_windows_in_docker.sh.
- macOS genuinely cannot. PyInstaller's osxcross/darling notes cover
  building its own C bootloader, not packaging a Python app: that still
  needs a macOS CPython plus macOS wheels for mediapipe, OpenCV and
  pygame. Use the hosted runner in .github/workflows/build-executables.yml
  (renting a Mac, not owning one).

Build with:  pyinstaller LMBox5.spec --noconfirm
or, preferably, via scripts/build_executable.py, which also names the
output per platform and drops it in bin/.
"""
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

SPEC_DIR = Path(SPECPATH)

sys.path.insert(0, str(SPEC_DIR))
from gui.version import __version__  # noqa: E402

# Everything the game loads at runtime by path. gui/gui.py builds these
# paths from its own __file__, which PyInstaller resolves inside the
# extraction directory, so the tree has to keep its "gui/resources/..."
# shape rather than being flattened.
datas = [("gui/resources", "gui/resources")]
binaries = []
hiddenimports = []

# mediapipe ships .tflite/.binarypb model graphs and a native extension
# alongside its Python code; without collecting the package wholesale the
# executable builds fine and then dies at the first hand/pose detection,
# because the models simply are not there. cvzone is collected for the
# same reason (it loads mediapipe's solutions through its own package
# data).
for package in ("mediapipe", "cvzone"):
    package_datas, package_binaries, package_hidden = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hidden

a = Analysis(
    ["main.py"],
    pathex=[str(SPEC_DIR)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    # Test-only and dev-only packages. pytest in particular drags in a
    # large dependency tree that no player will ever execute.
    excludes=["pytest", "_pytest", "tkinter", "IPython", "jupyter", "notebook"],
    noarchive=False,
)

pyz = PYZ(a.pure)

ICON = (
    str(SPEC_DIR / "build" / "icon.ico")
    if (SPEC_DIR / "build" / "icon.ico").exists()
    else None
)

# Shared EXE settings. A game, not a command-line tool, so no console window
# should appear behind it - flip `console` to True when chasing a crash that
# leaves no trace.
EXE_OPTIONS = dict(
    name="LMBox5",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON,
)

if sys.platform == "darwin":
    # onedir on macOS, unlike the single-file builds below, and not a
    # stylistic choice: PyInstaller warns that onefile "clashes with macOS's
    # security" inside a .app and will make it an outright error in v7. The
    # clash bites this app specifically. macOS grants camera access through
    # TCC, which identifies an app by its bundle - and a onefile bundle
    # unpacks itself to a fresh temporary directory and re-execs from there
    # on every launch, so the thing asking for the camera is not stably the
    # thing the user granted it to. A .app is a directory by nature; letting
    # it be one is what keeps the NSCameraUsageDescription prompt below
    # meaningful.
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, **EXE_OPTIONS)
    collected = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=False,
        name="LMBox5",
    )
else:
    # Linux and Windows: one self-contained file, which is what "download
    # and run it" should mean on those platforms.
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], runtime_tmpdir=None, **EXE_OPTIONS)

# macOS gates the camera behind TCC, and TCC only prompts for an .app
# bundle carrying an NSCameraUsageDescription. A bare Unix executable gets
# refused the camera with no prompt and no error the player can act on -
# which for this app means all three games silently fail to start.
if sys.platform == "darwin":
    app = BUNDLE(
        collected,
        name="LM Box 5.app",
        icon=None,
        bundle_identifier="com.lmbox5.game",
        version=__version__,
        info_plist={
            "NSCameraUsageDescription": (
                "LM Box 5 uses the camera to track your hands and body - "
                "that is how the games are played. Video never leaves your "
                "device."
            ),
            "NSHighResolutionCapable": True,
            "CFBundleShortVersionString": __version__,
        },
    )
