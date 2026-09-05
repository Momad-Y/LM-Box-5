# bin/

Where a build drops the standalone executable for the machine that built it:

```bash
pip install -r requirements-build.txt
python scripts/build_executable.py
```

produces something like `bin/LMBox5-v1.0.0-linux-x86_64` (~295 MB).

## Why the executables are not committed here

They are gitignored, and that is not a style preference - a 295 MB file
cannot be pushed to GitHub at all. GitHub warns above 50 MB and **hard-
rejects any file over 100 MB**, so committing these would break `git push`
outright. Git LFS would lift that limit but bills against a 1 GB free quota
that one release of three ~300 MB binaries would exhaust immediately, and
because git history is permanent, every past build would keep costing that
forever - including for anyone who only wanted to clone the source.

Built binaries are therefore published as **GitHub Release assets**, which
is what release assets are for: no size problem, no repo bloat, and a
stable download URL per version.
`.github/workflows/build-executables.yml` builds all three platforms and
attaches them automatically when a `v*` tag is pushed:

```bash
git tag v1.0.0 && git push origin v1.0.0
```

The size itself is unavoidable rather than careless: the bundle carries a
full Python interpreter, OpenCV, and MediaPipe's native runtime plus its
model graphs, because the whole point is that a player needs nothing
installed.

## One OS per build machine

PyInstaller does not cross-compile - it bundles the interpreter and native
libraries of the machine it runs on. A Windows `.exe` has to be built on
Windows and a macOS bundle on macOS; running `scripts/build_executable.py`
here only ever produces a build for *this* OS. That is why the release
workflow uses three runners.

## Per-platform notes

- **Linux** - a plain executable. `chmod +x` it after downloading. Built on
  Ubuntu 22.04 deliberately: a Linux binary links against the glibc it was
  built against and will not start on anything older.
- **Windows** - `.exe`, no console window. To see a crash, rebuild with
  `console=True` in `LMBox5.spec`.
- **macOS** - shipped as `LM Box 5.app` inside a zip, not a bare
  executable, because macOS only prompts for camera access for a bundle
  carrying `NSCameraUsageDescription` in its Info.plist. A plain binary is
  refused the camera with no prompt, which would leave all three games
  unable to start. The app is unsigned, so the first launch needs
  right-click -> Open.

## Where the game keeps its data

A frozen build does **not** write next to the executable - its own files
live in a temporary extraction directory that is deleted on exit. Settings,
the user database and captured photos go to the OS's per-user data
directory instead (`~/.local/share/LMBox5`, `~/Library/Application
Support/LMBox5`, `%LOCALAPPDATA%\LMBox5`). Running from source still uses
the repo's `data/`, so a checkout and an installed copy never fight over
the same files.
