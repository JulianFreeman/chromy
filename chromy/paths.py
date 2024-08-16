# coding: utf8
import os
import sys
from pathlib import Path

from jnp3.dict import get_with_chained_keys
from jnp3.path import path_exists


PLAT = sys.platform
USER_PATH = os.path.expanduser("~")

EXEC_PATH_MAP = {
    "win32": {
        "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        "edge": r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        "brave": r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
        "vivaldi": str(Path(USER_PATH, "AppData", "Local", "Vivaldi", "Application", "vivaldi.exe")),
        "yandex": str(Path(USER_PATH, "AppData", "Local", "Yandex", "YandexBrowser", "Application", "browser.exe")),
        "chromium": str(Path(USER_PATH, "AppData", "Local", "Chromium", "Application", "chrome.exe")),
    },
    "darwin": {
        "chrome": r"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "edge": r"/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        "brave": r"/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
        "vivaldi": r"/Applications/Vivaldi.app/Contents/MacOS/Vivaldi",
        "yandex": r"/Applications/Yandex.app/Contents/MacOS/Yandex",
        # "chromium": # 没有
    },
}

DATA_PATH_MAP = {
    "win32": {
        "chrome": str(Path(USER_PATH, "AppData", "Local", "Google", "Chrome", "User Data")),
        "edge": str(Path(USER_PATH, "AppData", "Local", "Microsoft", "Edge", "User Data")),
        "brave": str(Path(USER_PATH, "AppData", "Local", "BraveSoftware", "Brave-Browser", "User Data")),
        "vivaldi": str(Path(USER_PATH, "AppData", "Local", "Vivaldi", "User Data")),
        "yandex": str(Path(USER_PATH, "AppData", "Local", "Yandex", "YandexBrowser", "User Data")),
        "chromium": str(Path(USER_PATH, "AppData", "Local", "Chromium", "User Data")),
    },
    "darwin": {
        "chrome": str(Path(USER_PATH, "Library", "Application Support", "Google", "Chrome")),
        "edge": str(Path(USER_PATH, "Library", "Application Support", "Microsoft Edge")),
        "brave": str(Path(USER_PATH, "Library", "Application Support", "BraveSoftware", "Brave-Browser")),
        "vivaldi": str(Path(USER_PATH, "Library", "Application Support", "Vivaldi")),
        "yandex": str(Path(USER_PATH, "Library", "Application Support", "Yandex", "YandexBrowser")),
        "chromium": str(Path(USER_PATH, "Library", "Application Support", "Chromium")),
    },
}


def get_browser_exec_path(browser: str, missing_ok: bool = False) -> str | None:
    exec_path = get_with_chained_keys(EXEC_PATH_MAP, [PLAT, browser])  # type: str | None
    # 如果获取的是 None 则不管 missing ok 不 ok 都必须返回 None，因此不能跟下面的判断合并
    if exec_path is None:
        return None

    if missing_ok or path_exists(exec_path):
        return exec_path

    return None


def get_browser_data_path(browser: str, missing_ok: bool = False) -> str | None:
    data_path = get_with_chained_keys(DATA_PATH_MAP, [PLAT, browser])  # type: str | None
    if data_path is None:
        return None

    if missing_ok or path_exists(data_path):
        return data_path

    return None
