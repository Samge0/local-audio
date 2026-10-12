# -*- coding: utf-8 -*-
"""将 AUDIO_DIR 下全部 .m4a 极限转码为 Opus 48k 单声道 -> audio_opus/（同结构）。

流程：转码 -> 校验（数量+时长一致）-> 由调用方手动/自动 swap 目录。
转换是 CPU 密集，ThreadPool 并行加速。
"""
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from config import PROJECT_ROOT, settings

OUT_DIR = PROJECT_ROOT / "audio_opus"
BITRATE = os.environ.get("OPUS_BITRATE", "24k")


def transcode_one(src: Path, dst: Path) -> tuple[bool, str]:
    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = [settings.FFMPEG, "-hide_banner", "-loglevel", "error", "-y",
           "-i", str(src), "-vn",
           "-c:a", "libopus", "-b:a", BITRATE, "-ac", "1",
           str(dst)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)
    if r.returncode == 0 and dst.exists():
        return True, ""
    return False, r.stderr[:300]


def dur_of(p: Path) -> float | None:
    try:
        r = subprocess.run(
            [settings.FFPROBE, "-v", "error", "-show_entries", "format=duration",
             "-of", "json", str(p)],
            capture_output=True, text=True, timeout=20)
        return float(__import__("json").loads(r.stdout)["format"]["duration"])
    except Exception:
        return None


def main():
    if not settings.FFMPEG:
        raise SystemExit("ffmpeg 不可用（.env FFMPEG_PATH）")
    # 转码源 = AUDIO_DIR 里的 m4a；但 AUDIO_DIR 可能已指向 opus 目录（在线服务用），
    # 此时回落到项目根的 audio/（原始 m4a 提取目录）。
    src_dir = settings.AUDIO_DIR
    if src_dir.resolve() == OUT_DIR.resolve() or not list(src_dir.rglob("*.m4a")):
        fallback = PROJECT_ROOT / "audio"
        if fallback.exists() and list(fallback.rglob("*.m4a")):
            src_dir = fallback
    srcs = sorted(src_dir.rglob("*.m4a"))
    if not srcs:
        raise SystemExit(f"找不到 m4a 源（查过 {src_dir} 与 {PROJECT_ROOT/'audio'}）")
    print(f"待转码 {len(srcs)} 个 m4a ({src_dir}) -> Opus {BITRATE} 单声道, 输出 {OUT_DIR}")
    jobs = [(s, OUT_DIR / s.relative_to(src_dir).with_suffix(".opus"))
            for s in srcs]
    t0 = time.time()
    done = fail = 0
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(transcode_one, s, d): (s, d) for s, d in jobs}
        for i, (fut, (s, d)) in enumerate(futs.items(), 1):
            ok, err = fut.result()
            if ok:
                sm, dm = s.stat().st_size/1e6, d.stat().st_size/1e6
                print(f"[{i}/{len(jobs)}] OK {sm:6.1f}MB -> {dm:5.1f}MB ({sm/dm:4.1f}x): {d.name}", flush=True)
                done += 1
            else:
                print(f"[{i}/{len(jobs)}] FAIL: {s.name}\n  {err}", flush=True)
                fail += 1
    mins = (time.time()-t0)/60
    print(f"\n转码完成: ok={done} fail={fail} 耗时{mins:.1f}分钟")

    # 校验：数量 + 时长一致
    if fail == 0:
        bad = []
        for s, d in jobs:
            ds, dd = dur_of(s), dur_of(d)
            if ds is None or dd is None or abs(ds-dd) > 1.0:
                bad.append((s.name, ds, dd))
        if bad:
            print(f"校验失败（时长偏差>1s）: {bad[:5]}")
            sys.exit(1)
        ssz = sum(s.stat().st_size for s, _ in jobs)/1e9
        dsz = sum(d.stat().st_size for _, d in jobs)/1e9
        print(f"校验通过: {len(jobs)} 个文件时长全部一致; "
              f"{ssz:.2f}GB -> {dsz:.2f}GB (省 {(1-dsz/ssz)*100:.0f}%)")


if __name__ == "__main__":
    main()
