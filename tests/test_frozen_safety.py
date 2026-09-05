"""Things that work from source but break in a packaged executable.

A PyInstaller build runs the same Python code in a meaningfully different
environment, and the differences are silent: the app imports, opens a
window, plays a round, and then falls over on something the test suite
cannot see because the test suite runs from source.

This file pins down the ones already paid for. The first was `exit()` in
Game.quit_app(): `exit` is not a builtin, it is a convenience the `site`
module injects for interactive use, and a frozen app does not have it. From
source every quit worked; the built executable raised NameError on every
single quit path and could not shut down at all. 225 tests passed
throughout - only launching the actual binary found it.
"""
import ast
import pathlib

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
RUNTIME_DIRS = ("gui", "models")

# Injected by site.py for interactive convenience, absent under -S and in
# frozen builds. sys.exit / sys.breakpointhook are the real ones.
SITE_INJECTED_BUILTINS = {"exit", "quit", "copyright", "credits", "license"}


def _runtime_sources():
    for directory in RUNTIME_DIRS:
        for path in sorted((REPO_ROOT / directory).rglob("*.py")):
            yield path
    yield REPO_ROOT / "main.py"


def test_no_runtime_code_calls_a_site_injected_builtin():
    offenders = []
    for path in _runtime_sources():
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in SITE_INJECTED_BUILTINS
            ):
                offenders.append(
                    f"{path.relative_to(REPO_ROOT)}:{node.lineno} calls "
                    f"{node.func.id}() - use sys.{node.func.id}() instead"
                )

    assert not offenders, (
        "these work from source but raise NameError in a frozen build:\n"
        + "\n".join(offenders)
    )


def test_quit_app_exits_through_sys_exit():
    # The specific call the packaged build died on.
    source = (REPO_ROOT / "gui" / "gui.py").read_text()
    tree = ast.parse(source)
    game = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef) and node.name == "Game"
    )
    quit_app = next(
        node
        for node in ast.walk(game)
        if isinstance(node, ast.FunctionDef) and node.name == "quit_app"
    )
    body = ast.get_source_segment(source, quit_app)
    assert "sys.exit()" in body


def test_the_data_directory_moves_out_of_the_bundle_when_frozen(monkeypatch):
    # A frozen app's __file__ points inside a temp extraction directory that
    # is deleted on exit, so settings and the user database would be lost on
    # every run if the data directory were still resolved relative to it.
    from gui import gui as gui_mod

    monkeypatch.setattr(gui_mod.sys, "frozen", True, raising=False)
    frozen_dir = gui_mod._resolve_data_dir()

    monkeypatch.delattr(gui_mod.sys, "frozen", raising=False)
    source_dir = gui_mod._resolve_data_dir()

    assert frozen_dir != source_dir
    assert "LMBox5" in frozen_dir
    # Must not sit inside the PyInstaller extraction directory
    assert "_MEI" not in frozen_dir


def test_every_runtime_asset_is_declared_for_the_bundle():
    # The spec bundles gui/resources wholesale; if the app ever loads an
    # asset from outside that tree, the packaged build would 404 on it while
    # running fine from source.
    import re

    spec = (REPO_ROOT / "LMBox5.spec").read_text()
    assert '("gui/resources", "gui/resources")' in spec

    pattern = re.compile(r"""["']([^"']*resources/[^"']*\.[a-z0-9]{2,4})["']""")
    for path in _runtime_sources():
        for match in pattern.finditer(path.read_text()):
            reference = match.group(1)
            assert "resources/" in reference
            assert reference.replace("{CWD}/", "").startswith("resources/"), (
                f"{path.name} loads {reference}, which is outside the bundled "
                "gui/resources tree"
            )
