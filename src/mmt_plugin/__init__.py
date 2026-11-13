"""mmt-plugin: generate, build and test mmt-dpi protocol plugins."""

from importlib.metadata import version

__all__ = ["__version__"]

__version__: str = version("mmt-plugin")
