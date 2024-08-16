# coding: utf8
import json
import shutil
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
            print(f'[READ] [{local_state_file}] does not contain profile/info_cache')
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

    def _fetch_extensions_from_settings(self, ext_settings: dict, profile: Profile):
        for ext_id in ext_settings:
            if ext_id in self.extensions:
                profile.extensions.add(ext_id)
                self.extensions[ext_id].profiles.add(profile.id)
                continue

            extensions_dir = Path(profile.profile_dir, "Extensions")
            if not extensions_dir.is_dir():
                print(f'[READ] [{extensions_dir}] is not a directory or does not exist')
                continue
            profile.extensions_dir = str(extensions_dir)

            ext_set = ext_settings[ext_id]
            # path 不存在的就不算了，为空的判断不能并入下面的判断中
            ext_path: str = ext_set.get("path", "")
            if len(ext_path) == 0:
                continue
            # 以防万一，见下面 icon 路径的注释
            if ext_path.startswith("/"):
                ext_path = ext_path[1:]

            if ext_path.startswith(ext_id):
                # 是应用商店安装的插件
                manifest_data = ext_set.get("manifest", {})
                icon_parent_path = extensions_dir / ext_path
            elif path_exists(ext_path):
                # 可能是离线安装的插件，也可能不是
                manifest_file = Path(ext_path, "manifest.json")
                if not manifest_file.exists():
                    # 可能是些内部的插件，但是路径有问题
                    continue

                manifest_data = json.loads(manifest_file.read_text(encoding="utf-8"))
                icon_parent_path = Path(ext_path)
            else:
                # 可能是一些内部插件，没有完整信息，就不管了
                continue

            icons_info: dict = manifest_data.get("icons", {})
            icon_short_path = icons_info.get(str(max(map(int, icons_info.keys()), default="")), "")
            # 如果以 / 开头，会被 Path 转成根路径，所以去掉
            if icon_short_path.startswith("/"):
                icon_short_path = icon_short_path[1:]
            icon_path = icon_parent_path / icon_short_path

            self.extensions[ext_id] = Extension(
                id=ext_id,
                name=manifest_data.get("name", ""),
                description=manifest_data.get("description", ""),
                icon=str(icon_path) if icon_path.is_file() else "",
                profiles={profile.id, },
            )
            profile.extensions.add(ext_id)

    def _fetch_extensions_from_preferences(self, either_pref_file: Path, profile: Profile):
        try:
            either_pref_data: dict = json.loads(either_pref_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print(f'[READ] [{either_pref_file}] is not valid JSON')
            return

        ext_settings: dict[str, dict] = get_with_chained_keys(either_pref_data, ["extensions", "settings"])
        if ext_settings is None:
            # 怪烦人的，不要了，一般也用不到
            # print(f'[READ] [{either_pref_file}] does not contain extensions/settings')
            return

        self._fetch_extensions_from_settings(ext_settings, profile)

    # 这里一定要从两个设置文件获取插件，是因为这一步同时也要
    # 确保 Preferences 和 Secure Preferences 文件都填充到 Profile 中
    # 貌似功能有点不单一，不过就这样吧

    def _fetch_extensions_in_pref(self, profile: Profile):
        pref_file = Path(profile.profile_dir, "Preferences")
        if not pref_file.is_file():
            print(f'[READ] [{pref_file}] is not a file or does not exist')
            return
        profile.pref_file = str(pref_file)

        self._fetch_extensions_from_preferences(pref_file, profile)

    def _fetch_extensions_in_secure_pref(self, profile: Profile):
        secure_pref_file = Path(profile.profile_dir, "Secure Preferences")
        if not secure_pref_file.is_file():
            print(f'[READ] [{secure_pref_file}] is not a file or does not exist')
            return
        profile.secure_pref_file = str(secure_pref_file)

        self._fetch_extensions_from_preferences(secure_pref_file, profile)

    def fetch_extensions_from_all_profiles(self):
        self.extensions.clear()
        for profile_id in self.profiles:
            profile = self.profiles[profile_id]

            self._fetch_extensions_in_pref(profile)  # 一般来说这里是没有插件的，为了兼容考虑
            self._fetch_extensions_in_secure_pref(profile)

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
                print(f'[READ] [{bookmark_file}] does not contain roots')
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

    def delete_bookmarks(self, urls_to_delete: list[str], profile_ids: list[str] = None):
        # 原理参考删除插件的函数注释
        default_profile_ids = set()
        for url in urls_to_delete:
            if url in self.bookmarks:
                default_profile_ids = set(self.bookmarks[url].profiles.keys()).union(default_profile_ids)

        if profile_ids is None:
            profile_ids = default_profile_ids
        else:
            profile_ids = default_profile_ids.intersection(profile_ids)

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

    def _delete_extension_from_preferences(
            self,
            either_pref_file: Path,
            ext_ids: list[str],
            profile: Profile,
            special_parts_path: list[str],  # 要么是 ["protection", "macs", ...] 要么是 [..., "pinned_extensions"]
    ):
        # 在 Secure Preferences 或者 Preferences 中删除插件数据

        try:
            either_pref_data: dict = json.loads(either_pref_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print(f'[DELETE] [{either_pref_file}] is not valid JSON')
            return

        ext_settings: dict[str, dict] = get_with_chained_keys(either_pref_data, ["extensions", "settings"])
        if ext_settings is not None:
            for ext_id in ext_ids:
                if ext_id in ext_settings:
                    ext_settings.pop(ext_id)
                    # 更新 Profiles
                    if ext_id in profile.extensions:
                        profile.extensions.remove(ext_id)
                    # 更新 Extensions
                    if ext_id in self.extensions and profile.id in self.extensions[ext_id].profiles:
                        self.extensions[ext_id].profiles.remove(profile.id)
                        if len(self.extensions[ext_id].profiles) == 0:
                            self.extensions.pop(ext_id)
                    print(f"[DELETE] deleted {ext_id} from {profile.id}")
        # else:
            # 太多信息，不要了
            # print(f'[DELETE] [{either_pref_file}] does not contain extensions/settings, maybe check another')

        # 要么是 ["protection", "macs", "extensions", "settings"] 要么是 ["extensions", "pinned_extensions"]
        special_parts: dict[str, str] | list[str] = get_with_chained_keys(either_pref_data, special_parts_path)
        if special_parts is not None:
            # 没办法，一个是字典，一个是列表，两者的删除方法不一样
            if isinstance(special_parts, list):
                delete_func = special_parts.remove
            else:
                delete_func = special_parts.pop

            for ext_id in ext_ids:
                if ext_id in special_parts:
                    delete_func(ext_id)
        # else:
            # 太多信息，不要了
            # print(f'[DELETE] [{either_pref_file}] does not contain {"/".join(special_parts_path)}')

        either_pref_file.write_text(json.dumps(either_pref_data, ensure_ascii=False, indent=4), encoding="utf-8")

    def _delete_extensions_in_secure_pref(self, ext_ids: list[str], profile: Profile):
        if len(profile.secure_pref_file) == 0:
            return
        secure_pref_file = Path(profile.secure_pref_file)

        self._delete_extension_from_preferences(
            secure_pref_file,
            ext_ids,
            profile,
            ["protection", "macs", "extensions", "settings"],
        )

    def _delete_extensions_in_pref(self, ext_ids: list[str], profile: Profile):
        if len(profile.pref_file) == 0:
            return
        pref_file = Path(profile.pref_file)

        self._delete_extension_from_preferences(
            pref_file,
            ext_ids,
            profile,
            ["extensions", "pinned_extensions"],
        )

    @staticmethod
    def _delete_extensions_from_disk(ext_ids: list[str], profile: Profile):
        if len(profile.extensions_dir) == 0:
            return

        for ext_id in ext_ids:
            ext_dir = Path(profile.extensions_dir, ext_id)
            # 如果是离线装的，这个路径就是不存在的，不过我们也不删离线插件的源插件包
            if ext_dir.exists():
                shutil.rmtree(ext_dir, ignore_errors=True)

    def delete_extensions(self, ext_ids_to_delete: list[str], profile_ids: list[str] = None):
        # 若插件A存在于 1、2、3，插件B存在于 2、3、4，那么一共要操作的用户是 1、2、3、4
        # 这里是取并集
        default_profile_ids = set()
        for ext_id in ext_ids_to_delete:
            if ext_id in self.extensions:
                default_profile_ids = self.extensions[ext_id].profiles.union(default_profile_ids)

        # 但是如果指定了可操作的用户范围，比如只处理 2、3 两个用户的，那么就是取交集了
        if profile_ids is None:
            profile_ids = default_profile_ids
        else:
            profile_ids = default_profile_ids.intersection(profile_ids)

        for profile_id in profile_ids:
            profile = self.profiles[profile_id]
            self._delete_extensions_in_secure_pref(ext_ids_to_delete, profile)
            self._delete_extensions_in_pref(ext_ids_to_delete, profile)
            self._delete_extensions_from_disk(ext_ids_to_delete, profile)
