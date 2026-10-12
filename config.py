# -*- coding: utf-8 -*-
"""统一配置：解析 .env，提供全项目唯一的路径/端口配置入口。

用法：
    from config import settings
    settings.COURSE_SRC_DIR  # Path
    settings.AUDIO_DIR       # Path
    settings.FFMPEG          # str | None

所有模块禁止硬编码本地绝对路径，一律从这里引用。
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


def _path_from_env(key: str, default: Path | None) -> Path | None:
    raw = os.getenv(key, "").strip()
    return Path(raw) if raw else default


@dataclass(frozen=True)
class Settings:
    """项目配置（不可变，启动时确定）。"""

    # --- 源与输出 ---
    COURSE_SRC_DIR: Path          # 视频课程源目录
    AUDIO_DIR: Path               # 音频输出目录
    CACHE_DIR: Path               # 本地测试/临时产物（git 忽略）

    # --- 工具链 ---
    FFMPEG: str | None            # None = 用 PATH 里的
    FFPROBE: str | None

    # --- 服务 ---
    PORT: int

    # --- 派生路径（field(init=False)）---
    DURATIONS_CACHE: Path = field(init=False)
    STATUS_FILE: Path = field(init=False)
    INDEX_HTML: Path = field(init=False)

    @staticmethod
    def load() -> "Settings":
        return Settings(
            COURSE_SRC_DIR=_path_from_env(
                "COURSE_SRC_DIR", PROJECT_ROOT / "course_src"),
            AUDIO_DIR=_path_from_env("AUDIO_DIR", PROJECT_ROOT / "audio"),
            CACHE_DIR=_path_from_env("CACHE_DIR", PROJECT_ROOT / ".cache"),
            FFMPEG=os.getenv("FFMPEG_PATH", "").strip() or shutil.which("ffmpeg"),
            FFPROBE=os.getenv("FFPROBE_PATH", "").strip() or shutil.which("ffprobe"),
            PORT=int(os.getenv("KAUDIO_PORT", "").strip() or "8792"),
        )

    def __post_init__(self):
        object.__setattr__(self, "DURATIONS_CACHE", self.CACHE_DIR / "durations.json")
        object.__setattr__(self, "STATUS_FILE", self.CACHE_DIR / "extract_status.json")
        object.__setattr__(self, "INDEX_HTML", PROJECT_ROOT / "index.html")


settings = Settings.load()
