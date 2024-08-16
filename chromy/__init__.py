# coding: utf8
from .chromi import ChromInstance
from .structs import Extension, Bookmark, Profile
from .paths import get_browser_data_path, get_browser_exec_path

__version__ = '0.1.2'
__version__info__ = tuple(map(int, __version__.split(".")))


__all__ = ["ChromInstance", "Extension", "Bookmark", "Profile",
           "get_browser_exec_path", "get_browser_data_path"]
