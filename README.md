# Audio Player

本地音频库的 WebUI 播放器，把任意音频文件按目录结构放入音频目录即可播放。

## 功能

- **播放列表**：按目录分组自然排序、实时搜索、每首显示总时长与已听进度
- **进度记忆**：记住每首的上次播放位置 + 上次播放的曲目，刷新/重开自动恢复
- **倍速播放**：0.1 ~ 4.0（预设 0.5/0.75/1/1.25/1.5/1.75/2/2.5/3/4 + ±0.1 微调），全局记忆
- **播放模式**：顺序 / 列表循环 / 单曲循环 / 随机
- **其他**：±15s 快进退、定时停止（5~60 分钟）、键盘快捷键（空格 / ←→ / ↑↓）、深色模式自适应
- **Mac 风格 UI**：毛玻璃窗口、交通灯、60s/圈慢速黑胶唱片、移动端自适应（≤899px 播放器置顶）

## 快速开始

### 1. 创建虚拟环境（uv + Python 3.13）

```bash
# 安装 uv（已装可跳过）
# Windows: powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
# macOS/Linux: curl -LsSf https://astral.sh/uv/install.sh | sh

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

### 3. 配置

```bash
cp .env.example .env    # Windows: copy .env.example .env
```

编辑 `.env`，设置 `AUDIO_DIR`（音频文件目录）。所有路径/端口统一在 `.env` 配置，由 `config.py` 解析，代码中零硬编码路径。

### 4. 放入音频

把音频文件（`.m4a` / `.mp3` / `.opus` / `.ogg` / `.flac` 等）按任意目录结构放入 `AUDIO_DIR`（默认 `./audio`），子目录会自动成为播放列表的分组。

### 5. 启动

```bash
python server.py
# 或 Windows 双击 启动.bat
```

打开 <http://127.0.0.1:8792>（端口可在 `.env` 改 `KAUDIO_PORT`）。手机同局域网访问 `http://<电脑IP>:8792`。

## 项目结构

```
.
├── config.py           # 统一配置：解析 .env → settings（全项目唯一路径来源）
├── server.py           # 后端：静态文件 + /api/list + 音频 Range 流式
├── static/             # 前端
│   ├── index.html      # 结构
│   ├── css/style.css   # 样式
│   └── js/app.js       # 逻辑
├── requirements.txt    # pip 依赖（带版本号）
├── .env.example        # 环境变量模板（复制为 .env 使用）
├── 启动.bat            # Windows 一键启动
├── .cache/             # git 忽略：本地测试产物 + 测试脚本 + 一次性临时脚本
└── audio/              # 音频资产（git 忽略，体积大）
```

## 配置项（.env）

| 变量 | 说明 | 默认 |
|---|---|---|
| `AUDIO_DIR` | 音频目录 | `./audio` |
| `KAUDIO_PORT` | 服务器端口 | `8792` |
| `FFPROBE_PATH` | ffprobe 路径（探测总时长用，留空用 PATH） | PATH 查找 |
| `CACHE_DIR` | 本地测试产物目录 | `./.cache` |

## API

| 端点 | 说明 |
|---|---|
| `GET /api/list` | 播放列表（含每首总时长 `dur` 秒，缓存于 `.cache/durations.json`） |
| `GET /audio/<path>` | 音频流（支持 Range，拖动进度条秒响应） |
