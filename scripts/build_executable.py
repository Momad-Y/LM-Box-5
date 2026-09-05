#!/usr/bin/env python3
"""Build the standalone LM Box 5 executable for whichever OS runs this.

    python scripts/build_executable.py

PyInstaller bundles the interpreter and native libraries of the machine it
runs on, so this cannot produce all three platforms from one box: run it on
Linux for the Linux build, on Windows for the .exe, on macOS for the .app.
.github/workflows/release.yml does exactly that across three runners.

The result is copied into bin/ under a name that says what it is, e.g.
bin/LMBox5-v1.0.0-linux-x86_64.
"""
import argparse
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from gui.version import __version__  # noqa: E402

BIN_DIR = REPO_ROOT / "bin"
BUILD_DIR = REPO_ROOT / "build"
DIST_DIR = REPO_ROOT / "dist"
ICON_SOURCE = REPO_ROOT / "gui" / "resources" / "images" / "5-lmbox-icon.png"


def platform_tag():
    """A short, unambiguous name for the machine being built for."""
    system = {"Linux": "linux", "Darwin": "macos", "Windows": "windows"}.get(
        platform.system(), platform.system().lower()
    )
    machine = platform.machine().lower()
    # Normalise the several spellings of 64-bit Intel so artifact names
    # don't differ between a GitHub runner and a local build.
    machine = {"x86_64": "x86_64", "amd64": "x86_64", "arm64": "arm64"}.get(
        machine, machine
    )
    return f"{system}-{machine}"


def build_icon():
    """Convert the app icon to .ico, which is what Windows builds embed.

    Skipped silently if Pillow or the source icon is unavailable - an
    executable without an icon is a cosmetic loss, not a failed build.
    """
    if not ICON_SOURCE.exists():
        return None
    try:
        from PIL import Image
    except ImportError:
        print("note: Pillow unavailable, building without an icon")
        return None

    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    target = BUILD_DIR / "icon.ico"
    image = Image.open(ICON_SOURCE).convert("RGBA")
    image.save(target, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (256, 256)])
    return target


def run_pyinstaller():
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        str(REPO_ROOT / "LMBox5.spec"),
        "--noconfirm",
        "--distpath",
        str(DIST_DIR),
        "--workpath",
        str(BUILD_DIR / "pyinstaller"),
    ]
    print("$ " + " ".join(command))
    subprocess.run(command, check=True, cwd=REPO_ROOT)


def archive_macos_app(app_path, destination):
    """Zip the .app - a bundle is a directory, and copying it around
    loose (or through a browser download) loses the executable bit."""
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        for item in app_path.rglob("*"):
            archive.write(item, item.relative_to(app_path.parent))
    return destination


def collect_artifact():
    """Move what PyInstaller produced into bin/ under a descriptive name."""
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    tag = platform_tag()
    stem = f"LMBox5-v{__version__}-{tag}"

    app_bundle = DIST_DIR / "LM Box 5.app"
    if app_bundle.exists():
        target = BIN_DIR / f"{stem}.app.zip"
        archive_macos_app(app_bundle, target)
        return target

    produced = DIST_DIR / ("LMBox5.exe" if os.name == "nt" else "LMBox5")
    if not produced.exists():
        raise SystemExit(f"PyInstaller produced nothing at {produced}")

    target = BIN_DIR / (f"{stem}.exe" if os.name == "nt" else stem)
    shutil.copy2(produced, target)
    target.chmod(target.stat().st_mode | 0o111)
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="only collect an already-built dist/ artifact into bin/",
    )
    args = parser.parse_args()

    if not args.skip_build:
        build_icon()
        run_pyinstaller()

    artifact = collect_artifact()
    size_mb = artifact.stat().st_size / (1024 * 1024)
    print(f"\nBuilt {artifact.relative_to(REPO_ROOT)}  ({size_mb:.0f} MB)")


if __name__ == "__main__":
    main()
