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
git tag vX.Y.Z && git push origin vX.Y.Z    # matching gui/version.py
```

The size itself is unavoidable rather than careless: the bundle carries a
full Python interpreter, OpenCV, and MediaPipe's native runtime plus its
model graphs, because the whole point is that a player needs nothing
installed.

## Do you need three machines? Only one, plus a rented Mac

PyInstaller does not cross-compile - it bundles the interpreter and native
libraries of the machine it runs on - so `scripts/build_executable.py` only
ever builds for the OS running it. But that does not mean three machines:

**Windows from Linux: yes.** Not by cross-compiling, but by side-stepping
it - run a *real* Windows Python under Wine in a container, so PyInstaller
believes it is on Windows, pip fetches `win_amd64` wheels, and the
bootloader stamped on is the Windows one:

```bash
./scripts/build_windows_in_docker.sh     # -> bin/LMBox5-*-windows-x86_64.exe
```

The output is a genuine `PE32+ executable (GUI), x86-64`, and it has been
launched back under Wine far enough to confirm MediaPipe's bundled model
graphs load - the failure mode that matters, since a build missing them
starts fine and then dies at the first hand detection.

The container's Python version is pinned to 3.12 on purpose. On 3.13 this
project's pins are simply not installable: `numpy==1.26.4` has no 3.13
wheels (2.1+ only), and `cvzone==1.6.1` has no 3.13 wheel at all - only
2.0.0, which is a different API from the 1.6.x this code targets. Matching
the interpreter to the pins is what keeps the Windows build the same
application as the Linux one rather than a lookalike on other libraries.

**macOS from Linux: no - but you still do not need to own a Mac.** The
options, in the order worth trying them:

1. **A hosted runner - already set up, and free here.** The `macos-14` job
   in `.github/workflows/build-executables.yml` builds on real Apple
   hardware on every `v*` tag. GitHub Actions is free with no minute limit
   for public repositories, which this one is, so this costs nothing.
2. **A rented Mac**, if you want an interactive machine to debug on rather
   than a build pipeline - MacinCloud is around $1/hour or $4/day,
   MacStadium and AWS EC2 Mac are the heavier options.
3. **macOS in a VM on Linux** (Docker-OSX / OSX-KVM) technically works and
   people do use it for builds, but Apple's licence permits macOS only on
   Apple hardware, so it is a licence violation rather than a grey area of
   engineering. Not something to build a publicly distributed binary on.
4. **Darling**, the macOS equivalent of the Wine trick used above, is the
   one that would be genuinely elegant and is not ready: CLI tooling works,
   GUI support is early, and it still needs macOS system files that only
   Apple can license to you.

What is *not* an option is cross-compiling. PyInstaller's osxcross and
darling references cover building its own C bootloader, not packaging a
Python app - that still needs a macOS CPython plus macOS wheels for
MediaPipe, OpenCV and pygame.

Note the macOS build is Apple Silicon only, and not by choice: MediaPipe
publishes exactly one macOS wheel, `macosx_11_0_arm64`. No Intel macOS
build of it exists on PyPI, so an Intel Mac job could not install the app's
core dependency at all. Intel Mac users have to run from source.

The release workflow still builds Windows natively on a Windows runner
rather than through Wine. Wine is a good proxy - good enough to prove the
bundle works - but a native build is the one to ship.

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

## Icons

Each platform wants a different thing, and one of them wants nothing:

- **Windows** embeds `icon.ico` directly into the `.exe`.
- **macOS** carries `icon.icns` inside `LM Box 5.app`.
- **Linux** cannot. PyInstaller reports "Ignoring icon; supported only on
  Windows and macOS" - an ELF executable has nowhere to put one. The icon
  comes from the icon theme via a `.desktop` entry instead:

  ```bash
  ./scripts/install_linux_desktop.sh      # per-user, no root needed
  ```

Both icon files are generated by `scripts/build_executable.py` from
`gui/resources/images/5-lmbox-icon.png`, which is 2000x1671 - not square.
`.ico` and `.icns` are square formats, so it is padded onto a transparent
square rather than stretched: the first build embedded a 256x214 frame,
which Windows renders wrong because it expects square entries.

## Where the game keeps its data

A frozen build does **not** write next to the executable - its own files
live in a temporary extraction directory that is deleted on exit. Settings,
the user database and captured photos go to the OS's per-user data
directory instead (`~/.local/share/LMBox5`, `~/Library/Application
Support/LMBox5`, `%LOCALAPPDATA%\LMBox5`). Running from source still uses
the repo's `data/`, so a checkout and an installed copy never fight over
the same files.
