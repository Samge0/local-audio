# -*- coding: utf-8 -*-
"""统一配置：解析 .env，提供播放器唯一的路径/端口配置入口。

用法：
    from config import settings
    settings.AUDIO_DIR   # Path
    settings.FFPROBE     # str | None

播放器本体只关心：音频目录、端口、ffprobe（探测时长）。
提取/转码是一次性临时脚本（git 忽略），路径在各自脚本内用变量赋值，不走这里。
"""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent

# 加载 .env（不存在时静默跳过，全部走默认值）
load_dotenv(PROJECT_ROOT / ".env")


def _path_from_env(key: str, default: Path) -> Path:
    raw = os.getenv(key, "").strip()
    return Path(raw) if raw else default


@dataclass(frozen=True)
class Settings:
    """播放器配置（不可变，启动时确定）。"""

    AUDIO_DIR: Path               # 音频目录
    CACHE_DIR: Path               # 本地测试/临时产物（git 忽略）
    FFPROBE: str | None           # None = 用 PATH 里的
    PORT: int

    # --- 派生路径 ---
    DURATIONS_CACHE: Path = field(init=False)
    INDEX_HTML: Path = field(init=False)

    @staticmethod
    def load() -> "Settings":
        return Settings(
            AUDIO_DIR=_path_from_env("AUDIO_DIR", PROJECT_ROOT / "audio"),
            CACHE_DIR=_path_from_env("CACHE_DIR", PROJECT_ROOT / ".cache"),
            FFPROBE=os.getenv("FFPROBE_PATH", "").strip() or shutil.which("ffprobe"),
            PORT=int(os.getenv("KAUDIO_PORT", "").strip() or "8792"),
        )

    def __post_init__(self):
        object.__setattr__(self, "DURATIONS_CACHE", self.CACHE_DIR / "durations.json")
        object.__setattr__(self, "INDEX_HTML", PROJECT_ROOT / "static" / "index.html")


settings = Settings.load()
