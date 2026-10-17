# -*- coding: utf-8 -*-
"""通用音频播放器 - 后端。

扫描 AUDIO_DIR（保持目录结构）提供播放列表；
静态文件 + /api/* 路由；音频走独立流式 handler，支持 Range（拖动进度条必需）。
路径/端口全部来自 config.settings（.env 可覆盖）。
"""
from __future__ import annotations

import json
import re
import subprocess
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from config import PROJECT_ROOT, settings

AUDIO_URL_PREFIX = "/audio/"
AUDIO_EXT = {".mp3", ".m4a", ".aac", ".ogg", ".wav", ".flac", ".opus"}
SUB_EXT = {".vtt"}  # 浏览器字幕（同目录同名 .srt/.ass 等已由临时脚本统一转成 vtt）
CTYPES = {".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".aac": "audio/aac",
          ".ogg": "audio/ogg", ".wav": "audio/wav", ".flac": "audio/flac",
          ".opus": "audio/opus"}
_dur_cache: dict[str, dict] = {}  # id -> {"m": mtime, "s": size, "d": duration_sec}


def _probe_dur(p: Path) -> float | None:
    """ffprobe 取总时长（秒），失败返回 None。"""
    if not settings.FFPROBE:
        return None
    try:
        r = subprocess.run(
            [settings.FFPROBE, "-v", "error", "-show_entries", "format=duration",
             "-of", "json", str(p)],
            capture_output=True, text=True, timeout=20)
        if r.returncode == 0:
            return round(float(json.loads(r.stdout)["format"]["duration"]), 1)
    except Exception:
        pass
    return None


def _load_dur_cache():
    try:
        global _dur_cache
        _dur_cache = json.loads(settings.DURATIONS_CACHE.read_text("utf-8"))
    except Exception:
        _dur_cache = {}


def _save_dur_cache():
    try:
        settings.DURATIONS_CACHE.parent.mkdir(parents=True, exist_ok=True)
        settings.DURATIONS_CACHE.write_text(
            json.dumps(_dur_cache, ensure_ascii=False), "utf-8")
    except Exception:
        pass


def scan_audio() -> list[dict]:
    """返回 [{id, name, group, size, ext, url, sub}]，按目录分组自然排序。
    sub = 同名字幕的 vtt URL（含 ffmpeg 转换产物），无字幕为 null。"""
    SUB_EXTS = (".srt", ".ass", ".ssa", ".sub", ".vtt")
    items = []
    audio_dir = settings.AUDIO_DIR
    if audio_dir.exists():
        for p in audio_dir.rglob("*"):
            if p.is_file() and p.suffix.lower() in AUDIO_EXT:
                rel = p.relative_to(audio_dir)
                parts = rel.parts
                group = " / ".join(parts[:-1]) if len(parts) > 1 else ""
                stem = parts[-1][: -len(p.suffix)]
                rid = urllib.parse.quote(str(rel).replace("\\", "/"), safe="")
                # 同名字幕探测：多点多扩展名文件名（"1.第1章-x.opus"）不能用 with_suffix
                sub = None
                name_no_ext = p.name[: -len(p.suffix)]
                for ext in SUB_EXTS:
                    if (p.parent / (name_no_ext + ext)).exists():
                        vtt_rel = str(rel.parent / (stem + ".vtt")).replace("\\", "/") if rel.parent else stem + ".vtt"
                        sub = AUDIO_URL_PREFIX + urllib.parse.quote(vtt_rel, safe="")
                        break
                items.append({
                    "id": rid,
                    "name": stem,
                    "group": group,
                    "size": p.stat().st_size,
                    "ext": p.suffix.lower().lstrip("."),
                    "url": AUDIO_URL_PREFIX + rid,
                    "sub": sub,
                })

    def natkey(it):
        return (it["group"],
                [int(t) if t.isdigit() else t.lower()
                 for t in re.split(r"(\d+)", it["name"])])
    items.sort(key=natkey)
    return items


def scan_audio_with_dur() -> list[dict]:
    """scan_audio + 每项附 dur（秒）。mtime/size 变化才重新 ffprobe。"""
    items = scan_audio()
    cache = dict(_dur_cache)

    def cached_dur(it: dict):
        c = cache.get(it["id"])
        p = settings.AUDIO_DIR / urllib.parse.unquote(it["id"])
        try:
            st = p.stat()
        except OSError:
            return None
        if c and c.get("m") == st.st_mtime and c.get("s") == st.st_size:
            it["dur"] = c["d"]
            return None
        return st

    todo = [(it, st) for it in items if (st := cached_dur(it)) is not None]
    if todo:
        with ThreadPoolExecutor(max_workers=8) as ex:
            futs = {
                ex.submit(_probe_dur, settings.AUDIO_DIR / urllib.parse.unquote(it["id"])): (it, st)
                for it, st in todo}
            for fut, (it, st) in futs.items():
                d = fut.result()
                if d is not None:
                    it["dur"] = d
                    _dur_cache[it["id"]] = {"m": st.st_mtime, "s": st.st_size, "d": d}
        _save_dur_cache()
    for it in items:
        it.setdefault("dur", None)
    return items


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(PROJECT_ROOT), **kw)

    # --- 工具 ---
    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass  # 静默访问日志

    def _resolve_audio(self, path: str) -> Path | None:
        """path 形如 /audio/<percent-encoded rel>；安全解析到 AUDIO_DIR 内文件。"""
        enc = path[len(AUDIO_URL_PREFIX):]
        rel = urllib.parse.unquote(enc)
        base = settings.AUDIO_DIR.resolve()
        p = (base / rel).resolve()
        try:
            p.relative_to(base)
        except ValueError:
            return None  # 目录穿越
        if p.is_file() and p.suffix.lower() in AUDIO_EXT | SUB_EXT:
            return p
        return None

    def _stream_audio(self, p: Path):
        size = p.stat().st_size
        ctype = CTYPES.get(p.suffix.lower(),
                           "text/vtt; charset=utf-8" if p.suffix.lower() == ".vtt"
                           else "application/octet-stream")
        rng = self.headers.get("Range")
        start, end = 0, size - 1
        partial = False
        if rng and rng.startswith("bytes="):
            m = re.match(r"bytes=(\d*)-(\d*)", rng)
            if m:
                start = int(m.group(1) or 0)
                end = int(m.group(2) or size - 1)
                end = min(end, size - 1)
                partial = True
        if start > end or start >= size:
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{size}")
            self.end_headers()
            return
        length = end - start + 1
        self.send_response(206 if partial else 200)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        if partial:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(length))
        self.end_headers()
        try:
            with open(p, "rb") as f:
                f.seek(start)
                remaining = length
                while remaining > 0:
                    chunk = f.read(min(256 * 1024, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass  # 客户端断开（拖动进度条常见）

    # --- 工具 ---
    def _send_bytes(self, body: bytes, ctype: str, cache: str = "no-store"):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache)
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass  # 客户端提前断开（健康检查/轮询超时常见），非服务端故障

    # --- 路由 ---
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path == "/api/list":
            items = scan_audio_with_dur()
            body = json.dumps({"ok": True, "count": len(items), "items": items},
                              ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass  # 健康检查/客户端超时断开，静默
            return
        if path.startswith(AUDIO_URL_PREFIX):
            p = self._resolve_audio(path)
            if p is None:
                return self._json({"ok": False, "error": "not found"}, 404)
            return self._stream_audio(p)
        if path in ("/", "/index.html", "/static/", "/static"):
            # 明确指向 static/index.html（此前用 PROJECT_ROOT 相对定位，
            # 项目目录改名 + 容器挂卷覆盖 /app/static 后存在回退到目录列表的风险）
            index = PROJECT_ROOT / "static" / "index.html"
            if index.exists():
                body = index.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                try:
                    self.wfile.write(body)
                except (BrokenPipeError, ConnectionResetError):
                    pass
                return
            # index 缺失：明确 404，绝不回退到 SimpleHTTPRequestHandler 的目录列表
            self.send_response(404)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"index not found")
            return
        # 其余路径走静态文件；仅对存在的具体文件放行，杜绝目录列表
        candidate = (PROJECT_ROOT / urllib.parse.unquote(path.lstrip("/"))).resolve()
        try:
            candidate.relative_to(PROJECT_ROOT.resolve())
        except ValueError:
            return self._json({"ok": False, "error": "forbidden"}, 403)
        if candidate.is_file():
            return super().do_GET()
        self.send_response(404)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"not found")

    def do_HEAD(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path.startswith(AUDIO_URL_PREFIX):
            p = self._resolve_audio(parsed.path)
            if p is None:
                self.send_response(404)
                self.end_headers()
                return
            size = p.stat().st_size
            self.send_response(200)
            self.send_header("Content-Type",
                             CTYPES.get(p.suffix.lower(), "application/octet-stream"))
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(size))
            self.end_headers()
            return
        super().do_HEAD()


def main():
    if not settings.AUDIO_DIR.exists():
        settings.AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    _load_dur_cache()
    items = scan_audio_with_dur()
    total_h = sum(i["dur"] or 0 for i in items) / 3600
    print(f"音频播放器: http://127.0.0.1:{settings.PORT}  (audio: {settings.AUDIO_DIR})")
    print(f"已发现 {len(items)} 个音频文件, 总时长 {total_h:.1f} 小时")
    httpd = ThreadingHTTPServer(("0.0.0.0", settings.PORT), Handler)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
