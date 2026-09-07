"""The single place the app's version number is written down.

Read by the build (to name the executables), by the Credits screen, and by
anything else that needs to say which build it is. Keeping it here rather
than in the packaging config means a source checkout and a frozen
executable always agree about what they are.
"""

__version__ = "1.0.2"

# Shown in the UI, where a bare number reads like a stray value.
VERSION_LABEL = f"v{__version__}"
