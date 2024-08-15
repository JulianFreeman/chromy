# coding: utf8
import json
from os import PathLike
from pathlib import Path

from jnp3.dict import get_with_chained_keys
from jnp3.path import path_exists

from .structs import Extension, Bookmark, Profile


class ChromInstance(object):

    def __init__(self, userdata_dir: str | PathLike[str]):
        self.userdata_dir = userdata_dir
        self.profiles: dict[str, Profile] = {}
        self.extensions: dict[str, Extension] = {}
        self.bookmarks: dict[str, Bookmark] = {}

    def fetch_all_profiles(self):
        userdata_dir: Path = Path(self.userdata_dir)
        if not userdata_dir.is_dir():
            print(f'[READ] [{userdata_dir}] is not a directory or does not exist')
            return

        local_state_file = userdata_dir / "Local State"
        if not local_state_file.is_file():
            print(f'[READ] [{local_state_file}] is not a file or does not exist')
            return

        try:
            local_state_data: dict = json.loads(local_state_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print(f'[READ] [{local_state_file}] is not valid JSON')
            return

        profiles_info: dict[str, dict] = get_with_chained_keys(local_state_data, ["profile", "info_cache"])
        if profiles_info is None:
            print(f'[READ] [{local_state_data}] does not contain profile/info_cache')
            return

        self.profiles.clear()
        for profile_id in profiles_info:
            profile_info = profiles_info[profile_id]
            profile = Profile(
                id=profile_id,
                name=profile_info.get("name", ""),
                user_name=profile_info.get("user_name", ""),
                gaia_name=profile_info.get("gaia_name", ""),
                gaia_given_name=profile_info.get("gaia_given_name", ""),
                userdata_dir=str(userdata_dir),
                profile_dir=str(userdata_dir / profile_id),  # 这里我们认为肯定存在
            )
            self.profiles[profile_id] = profile

    def _fetch_extensions_from_one_profile(self, ext_settings: dict, profile: Profile):
        for ext_id in ext_settings:
            if ext_id in self.extensions:
                profile.extensions.add(ext_id)
                self.extensions[ext_id].profiles.add(profile.id)
                continue

            ext_dir = Path(profile.profile_dir, "Extensions")
            if not ext_dir.is_dir():
                print(f'[READ] [{ext_dir}] is not a directory or does not exist')
                continue

            ext_set = ext_settings[ext_id]
            # path 不存在的就不算了，为空的判断不能并入下面的判断中
            ext_path = ext_set.get("path", "")
            if len(ext_path) == 0:
                continue

            if path_exists(ext_path):
                # 是离线安装的插件
                manifest_file = Path(ext_path, "manifest.json")
                manifest_data = json.loads(manifest_file.read_text(encoding="utf-8"))
                icon_parent_path = Path(ext_path)
            elif path_exists(ext_dir / ext_path):
                # 是在线安装的插件
                manifest_data = ext_set.get("manifest", {})
                icon_parent_path = ext_dir / ext_path
            else:
                # 可能是一些谷歌内部插件，没有完整信息，就不管了
                continue

            icons_info: dict = manifest_data.get("icons", {})
            icon_short_path = icons_info.get(str(max(map(int, icons_info.keys()), default="")), "")
            icon_path = icon_parent_path / icon_short_path

            self.extensions[ext_id] = Extension(
                id=ext_id,
                name=manifest_data.get("name", ""),
                description=manifest_data.get("description", ""),
                icon=str(icon_path) if icon_path.is_file() else "",
                profiles={profile.id, },
            )
            profile.extensions.add(ext_id)

    def fetch_extensions_from_all_profiles(self):
        self.extensions.clear()
        for profile_id in self.profiles:
            profile = self.profiles[profile_id]
            profile_dir = Path(profile.profile_dir)

            secure_pref_file = profile_dir / "Secure Preferences"
            if not secure_pref_file.is_file():
                print(f'[READ] [{secure_pref_file}] is not a file or does not exist')
                continue

            try:
                secure_pref_data: dict = json.loads(secure_pref_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                print(f'[READ] [{secure_pref_file}] is not valid JSON')
                continue

            ext_settings: dict[str, dict] = get_with_chained_keys(secure_pref_data, ["extensions", "settings"])
            if ext_settings is None:
                print(f'[READ] [{secure_pref_data}] does not contain extensions/settings')
                continue

            self._fetch_extensions_from_one_profile(ext_settings, profile)

    def _fetch_bookmarks_from_one_type(
            self,
            bookmark_info: dict,
            profile: Profile,
            path_ls: list[str],  # 每层父目录的列表，形如 ["", "书签栏", "工作", "AAA"]
    ):
        if bookmark_info["type"] == "url":
            # 这是一个单个书签
            url = bookmark_info["url"]
            bmk_path = '/'.join(path_ls)
            profile.bookmarks[url] = bmk_path

            if url in self.bookmarks:
                self.bookmarks[url].profiles[profile.id] = bmk_path
                return
            else:
                self.bookmarks[url] = Bookmark(
                    name=bookmark_info["name"],
                    url=bookmark_info["url"],
                    profiles={profile.id: bmk_path, }
                )
                return
        elif bookmark_info["type"] == "folder":
            new_path_ls = path_ls + [bookmark_info["name"]]
            for child in bookmark_info["children"]:
                self._fetch_bookmarks_from_one_type(child, profile, new_path_ls)

    def fetch_bookmarks_from_all_profiles(self):
        self.bookmarks.clear()
        for profile_id in self.profiles:
            profile = self.profiles[profile_id]
            profile_dir = Path(profile.profile_dir)

            bookmark_file = profile_dir / "Bookmarks"
            if not bookmark_file.is_file():
                # 如果一个浏览器没有书签，那么该文件就不存在
                print(f'[READ] [{bookmark_file}] is not a file or does not exist')
                continue
            profile.bookmark_file = str(bookmark_file)

            try:
                bookmark_data: dict = json.loads(bookmark_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                print(f'[READ] [{bookmark_file}] is not valid JSON')
                continue

            bookmarks_info: dict[str, dict] = get_with_chained_keys(bookmark_data, ["roots"])
            if bookmarks_info is None:
                print(f'[READ] [{bookmark_data}] does not contain roots')
                continue

            for bmk_type in bookmarks_info:
                bookmark_info = bookmarks_info[bmk_type]
                self._fetch_bookmarks_from_one_type(bookmark_info, profile, [""])

    def _delete_bookmarks_in_one_folder(self, bookmark_info: dict, urls_to_delete: list[str], profile: Profile):
        if bookmark_info["type"] != "folder":
            return

        children: list[dict] = bookmark_info["children"]
        # 倒序循环，防止弹出元素后索引混乱的问题
        for i in range(len(children) - 1, -1, -1):
            child = children[i]
            if child["type"] == "url":
                url = child["url"]
                if url in urls_to_delete:
                    children.pop(i)
                    # 更新 profiles
                    if url in profile.bookmarks:
                        profile.bookmarks.pop(url)
                    # 更新 bookmarks
                    if url in self.bookmarks and profile.id in self.bookmarks[url].profiles:
                        self.bookmarks[url].profiles.pop(profile.id)
                        # 如果没有任何用户有这个书签了，直接把书签删掉
                        if len(self.bookmarks[url].profiles) == 0:
                            self.bookmarks.pop(url)

                    print(f"[DELETE] deleted {url} from {profile.id}")
            else:
                self._delete_bookmarks_in_one_folder(child, urls_to_delete, profile)

    def delete_bookmarks_from_profiles(self, urls_to_delete: list[str], profile_ids: list[str] = None):
        # 删除书签总归还是要处理文件的，所以这里循环 profiles，而不是循环 bookmarks
        # 虽然看起来循环 bookmarks 更简单，但是这样就需要多次打开文件，
        # 或者维护一个 profile 到书签文件数据的字典，太繁琐

        if profile_ids is None:
            profile_ids = self.profiles.keys()

        for profile_id in profile_ids:
            profile = self.profiles[profile_id]

            # 删除可能的备份文件
            Path(profile.profile_dir, "Bookmarks.bak").unlink(missing_ok=True)

            if len(profile.bookmark_file) == 0:
                # 书签文件不存在
                continue
            bookmark_file = Path(profile.bookmark_file)

            try:
                bookmark_data: dict = json.loads(bookmark_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                print(f'[DELETE] [{bookmark_file}] is not valid JSON')
                continue

            if "checksum" in bookmark_data:
                bookmark_data.pop("checksum")

            if "roots" in bookmark_data:
                for bmk_root in bookmark_data["roots"]:
                    self._delete_bookmarks_in_one_folder(bookmark_data["roots"][bmk_root], urls_to_delete, profile)

            bookmark_file.write_text(json.dumps(bookmark_data, ensure_ascii=False, indent=4), encoding="utf-8")

    def search_bookmarks(self, url_contains: str, profile_ids: list[str] = None) -> dict[str, Bookmark]:
        if profile_ids is None:
            profile_ids = list(self.profiles.keys())

        filtered_bookmarks: dict[str, Bookmark] = {}
        for url in self.bookmarks:
            bookmark = self.bookmarks[url]
            if url_contains in url and len(set(bookmark.profiles.keys()).intersection(profile_ids)) != 0:
                filtered_bookmarks[url] = bookmark
        return filtered_bookmarks
