#!/usr/bin/env bash
# Build the Windows .exe from Linux (or macOS), without a Windows machine.
#
# PyInstaller genuinely cannot cross-compile - it bundles the interpreter and
# native libraries of the platform it runs on. The way around that is not to
# cross-compile at all: run a real Windows Python, under Wine, in a container.
# PyInstaller then thinks it is on Windows, pip pulls win_amd64 wheels, and
# the bootloader it stamps on is the Windows one.
#
#     ./scripts/build_windows_in_docker.sh
#
# Result: bin/LMBox5-v<version>-windows-x86_64.exe
#
# The image's Python version is pinned deliberately. requirements.txt pins
# numpy==1.26.4 and cvzone==1.6.1, and on Python 3.13 neither is installable
# (numpy has no 3.13 wheels below 2.1, and cvzone only publishes a 3.13 wheel
# for 2.0.0, which is a different API from the 1.6.x this code is written
# against). Matching the interpreter to the pins is what keeps the Windows
# build the same application as the Linux one rather than a lookalike built
# on different libraries.
set -euo pipefail

IMAGE="tobix/pywine:3.12"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "==> Building Windows executable in $IMAGE"

docker run --rm \
    -v "$REPO_ROOT":/src \
    -w /src \
    --entrypoint bash \
    "$IMAGE" -c '
set -euo pipefail

echo "--- Windows Python under Wine ---"
wine python --version

echo "--- installing dependencies (win_amd64 wheels) ---"
wine python -m pip install --quiet --upgrade pip
wine python -m pip install --quiet -r requirements.txt
wine python -m pip install --quiet -r requirements-build.txt

echo "--- building ---"
# Into a Windows-only working directory so a Linux build sitting in build/
# and dist/ is not clobbered by this one, and vice versa.
wine python -m PyInstaller LMBox5.spec --noconfirm \
    --distpath dist-windows \
    --workpath build/pyinstaller-windows

echo "--- collecting ---"
wine python scripts/build_executable.py --skip-build --dist dist-windows
'

echo
echo "==> Done:"
ls -la "$REPO_ROOT"/bin/*windows* 2>/dev/null || echo "no Windows artifact found"
