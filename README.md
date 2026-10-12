# K-Course Audio Player

程序员 K 哥 2.0 课程视频的音频提取 + Mac 风格 WebUI 播放器（单文件前端、零前端依赖、Python 标准库后端）。

![桌面版](.cache/shot-desktop.png)

## 功能

- **音频提取**：遍历源目录所有视频，AAC 音轨无损封装 `.m4a`（其他编码转 MP3），保持原目录结构，支持增量
- **播放列表**：按目录（老师）分组自然排序、实时搜索、每首显示总时长与已听进度
- **进度记忆**：记住每首的上次播放位置 + 上次播放的曲目，刷新/重开自动恢复
- **倍速播放**：0.1 ~ 4.0（预设 0.5/0.75/1/1.25/1.5/1.75/2/2.5/3/4 + ±0.1 微调）
- **播放模式**：顺序 / 列表循环 / 单曲循环 / 随机
- **其他**：±15s 快进退、定时停止（5~60 分钟）、键盘快捷键（空格 / ←→ / ↑↓）、深色模式自适应
- **Mac 风格 UI**：毛玻璃窗口、交通灯、60s/圈慢速黑胶唱片、移动端自适应（≤899px 播放器置顶）

## 快速开始

### 1. 创建虚拟环境（uv + Python 3.13）

```bash
# 安装 uv（已装可跳过）
# Windows: powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
# macOS/Linux: curl -LsSf https://astral.sh/uv/install.sh | sh

cd kcourse-audio
uv venv --python 3.13
```

### 2. 安装依赖

```bash
# Windows (PowerShell)
.venv\Scripts\activate
uv pip install -r requirements.txt

# macOS / Linux
source .venv/bin/activate
uv pip install -r requirements.txt
```

> 仅运行播放器本体只需要 `python-dotenv`；`playwright` / `pillow` 仅为测试与截图脚本所需。

### 3. 配置路径

```bash
cp .env.example .env    # Windows: copy .env.example .env
```

编辑 `.env`，设置 `COURSE_SRC_DIR`（视频课程源目录）等。所有路径/端口统一在 `.env` 配置，由 `config.py` 解析，代码中零硬编码路径。

### 4. 提取音频（可选，仓库已带 audio/ 的话跳过）

```bash
python extract_audio.py           # 增量提取（已存在跳过）
python extract_audio.py --force   # 强制全部重提
```

需要系统安装 [ffmpeg](https://ffmpeg.org/)（或 `.env` 里指定 `FFMPEG_PATH` / `FFPROBE_PATH`）。

### 5. 启动

```bash
python server.py
# 或 Windows 双击 启动.bat
```

打开 <http://127.0.0.1:8792>（端口可在 `.env` 改 `KAUDIO_PORT`）。手机同局域网访问 `http://<电脑IP>:8792`。

## 项目结构

```
kcourse-audio/
├── config.py           # 统一配置：解析 .env → settings（全项目唯一路径来源）
├── server.py           # 后端：静态文件 + /api/list + /api/status + 音频 Range 流式
├── extract_audio.py    # 音频提取（ffprobe 探测编码，AAC 无损 copy）
├── index.html          # 前端（单文件，无构建、无外部依赖）
├── requirements.txt    # pip 依赖（带版本号）
├── .env.example        # 环境变量模板（复制为 .env 使用）
├── 启动.bat            # Windows 一键启动
├── test_e2e.py         # Playwright E2E 回归（28 项）
├── test_ui.py          # DOM 级 UI 质检（16 项）
├── take_shots.py       # 截图工具（输出到 .cache/）
├── .cache/             # 本地测试产物（git 忽略）：截图、durations.json、extract_status.json
└── audio/              # 提取的音频（git 忽略，体积大）
```

## 配置项（.env）

| 变量 | 说明 | 默认 |
|---|---|---|
| `COURSE_SRC_DIR` | 视频课程源目录（提取用） | `./course_src` |
| `AUDIO_DIR` | 音频目录 | `./audio` |
| `KAUDIO_PORT` | 服务器端口 | `8792` |
| `FFMPEG_PATH` / `FFPROBE_PATH` | ffmpeg/ffprobe 路径（留空用 PATH） | PATH 查找 |
| `CACHE_DIR` | 本地测试产物目录 | `./.cache` |

## 测试

```bash
python test_e2e.py   # Playwright E2E：播放/记忆/倍速/搜索/上下首/模式/移动端
python test_ui.py    # DOM 质检：布局/断点/动画/像素
python take_shots.py # 生成截图到 .cache/
```

首次跑测试需 `playwright install chromium`。

## API

| 端点 | 说明 |
|---|---|
| `GET /api/list` | 播放列表（含每首总时长 `dur` 秒，缓存于 `.cache/durations.json`） |
| `GET /api/status` | 音频提取进度状态 |
| `GET /audio/<path>` | 音频流（支持 Range，拖动进度条秒响应） |
