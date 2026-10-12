# -*- coding: utf-8 -*-
"""遍历 COURSE_SRC_DIR 下所有视频 -> 提取音频到 AUDIO_DIR（保持目录结构）。

AAC 流直接 copy 进 m4a（无损、快）；其他编码转 mp3 128k。
进度状态写 CACHE_DIR/extract_status.json 供 WebUI 展示。
"""
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from config import settings

VIDEO_EXT = {".mp4", ".mkv", ".avi", ".mov", ".ts", ".flv", ".wmv", ".webm"}


def write_status(**kw):
    st = {"total": 0, "done": 0, "ok": 0, "fail": 0, "skip": 0,
          "current": "", "running": True,
          "updated": datetime.now().isoformat(timespec="seconds")}
    if settings.STATUS_FILE.exists():
        try:
            st.update(json.loads(settings.STATUS_FILE.read_text("utf-8")))
        except Exception:
            pass
    st.update(kw)
    settings.STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    settings.STATUS_FILE.write_text(json.dumps(st, ensure_ascii=False, indent=1), "utf-8")


def probe(path: Path):
    if not settings.FFPROBE:
        raise SystemExit("ffprobe 不可用：请安装 ffmpeg 或在 .env 设置 FFPROBE_PATH")
    r = subprocess.run(
        [settings.FFPROBE, "-v", "error", "-select_streams", "a:0",
         "-show_entries", "stream=codec_name",
         "-show_entries", "format=duration", "-of", "json", str(path)],
        capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        return None
    try:
        d = json.loads(r.stdout)
        s = d["streams"][0] if d.get("streams") else {}
        return {"codec": s.get("codec_name"),
                "dur": float(d.get("format", {}).get("duration", 0) or 0)}
    except Exception:
        return None


def build_cmd(codec: str, src: Path, out: Path) -> list[str]:
    if not settings.FFMPEG:
        raise SystemExit("ffmpeg 不可用：请安装 ffmpeg 或在 .env 设置 FFMPEG_PATH")
    if codec in ("aac", "mp3"):
        # 无损 copy（m4a 容器装 aac；mp3 保持 mp3）
        return [settings.FFMPEG, "-hide_banner", "-loglevel", "error", "-y",
                "-i", str(src), "-vn", "-c:a", "copy", str(out)]
    return [settings.FFMPEG, "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(src), "-vn",
            "-codec:a", "libmp3lame", "-b:a", "128k",
            "-ar", "44100", "-ac", "2", str(out)]


def main():
    force = "--force" in sys.argv
    src = settings.COURSE_SRC_DIR
    if not src.exists():
        raise SystemExit(f"源目录不存在: {src} （请在 .env 设置 COURSE_SRC_DIR）")
    videos = sorted(
        p for p in src.rglob("*")
        if p.is_file() and p.suffix.lower() in VIDEO_EXT)
    write_status(total=len(videos), done=0, ok=0, fail=0, skip=0, running=True)
    print(f"发现 {len(videos)} 个视频文件  (src={src})", flush=True)
    ok = fail = skip = 0
    t0 = time.time()
    for i, v in enumerate(videos, 1):
        rel = v.relative_to(src)
        write_status(done=i - 1, ok=ok, fail=fail, skip=skip, current=str(rel))
        info = probe(v)
        if info is None or not info.get("codec"):
            print(f"[{i}/{len(videos)}] 无音频流,跳过: {rel}", flush=True)
            skip += 1
            continue
        suffix = ".m4a" if info["codec"] == "aac" else ".mp3"
        out = settings.AUDIO_DIR / rel.with_suffix(suffix)
        if out.exists() and not force:
            print(f"[{i}/{len(videos)}] 已存在,跳过: {out.name}", flush=True)
            ok += 1
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        cmd = build_cmd(info["codec"], v, out)
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
        if r.returncode == 0 and out.exists():
            mb = out.stat().st_size / 1e6
            print(f"[{i}/{len(videos)}] OK {mb:6.1f}MB {info['dur']/60:5.0f}min: {rel}", flush=True)
            ok += 1
        else:
            print(f"[{i}/{len(videos)}] FAIL: {rel}\n  {r.stderr[:300]}", flush=True)
            fail += 1
    mins = (time.time() - t0) / 60
    write_status(done=len(videos), ok=ok, fail=fail, skip=skip, current="",
                 running=False,
                 finished_at=datetime.now().isoformat(timespec="seconds"))
    print(f"\n完成: ok={ok} fail={fail} skip={skip} 耗时{mins:.1f}分钟", flush=True)


if __name__ == "__main__":
    main()
