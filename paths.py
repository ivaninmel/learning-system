"""区分打包资源目录与用户可写数据目录。"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def resource_dir() -> Path:
    """返回随应用发布的只读资源根目录。"""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).parent


def data_dir() -> Path:
    """返回当前用户下可持续写入的应用数据目录。"""
    if getattr(sys, "frozen", False):
        root = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "学习小助手"
    else:
        root = resource_dir() / "data"
    root.mkdir(parents=True, exist_ok=True)
    return root
