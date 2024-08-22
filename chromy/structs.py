# coding: utf8
from dataclasses import dataclass, field


@dataclass
class Extension(object):
    id: str           # 插件的唯一编号，形如 cfnpidifppmenkapgihekkeednfoenal
    name: str         # 插件名称
    description: str  # 插件描述
    icon: str         # 插件图标绝对路径

    profiles: set[str] = field(default_factory=set)  # element: 形如 Profile 185


@dataclass
class Bookmark(object):
    name: str  # 书签名称
    url: str   # 书签链接，作为唯一标识

    profiles: dict[str, str] = field(default_factory=dict)  # key: Profile ID, value: 书签路径


@dataclass
class Profile(object):
    id: str                           # 浏览器的唯一编号，形如 Profile 185
    name: str                         # 浏览器用户名称
    user_name: str                    # 账号邮箱地址
    gaia_name: str                    # 谷歌账号全名
    gaia_given_name: str              # 谷歌账号单名
    avatar_icon: str                  # 默认图标名称
    default_avatar_fill_color: int    # 默认无图标时的填充色
    default_avatar_stroke_color: int  # 默认无图标时的前景色
    gaia_picture_file_name: str       # 头像图片路径，如果有

    userdata_dir: str           # 该用户的上层 User Data 路径，形如 .../User Data
    profile_dir: str            # 数据路径，形如 .../User Data/Profile 185
    extensions_dir: str = ""    # 插件路径，形如 .../User Data/Profile 185/Extensions
    bookmark_file: str = ""     # 书签路径，形如 .../User Data/Profile 185/Bookmarks，不存在则为空
    pref_file: str = ""         # 偏好设置路径，形如 .../User Data/Profile 185/Preferences
    secure_pref_file: str = ""  # 安全偏好设置路径，形如 .../User Data/Profile 185/Secure Preferences

    extensions: set[str] = field(default_factory=set)        # element: 形如 cfnpidifppmenkapgihekkeednfoenal
    bookmarks: dict[str, str] = field(default_factory=dict)  # key: url, value: 书签路径
