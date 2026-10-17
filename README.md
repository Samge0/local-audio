# Local Audio

> 🌐 **[项目主页](https://samge0.github.io/local-audio/)** — 一页看懂功能、快速开始与部署方式
>
> 📱 **[Android 客户端](https://github.com/Samge0/local-audio-android)** — 与 Web 版功能对等的安卓端，Releases 提供现成 APK

本地音频库的 WebUI 播放器，把任意音频文件按目录结构放入音频目录即可播放。
<img width="1280" height="800" alt="desktop-sub" src="https://github.com/user-attachments/assets/a0827e56-dfc6-4ead-852c-6319740670e4" />

## 功能

- **播放列表**：按目录分组自然排序、实时搜索、每首显示总时长与已听进度
- **进度记忆**：记住每首的上次播放位置 + 上次播放的曲目，刷新/重开自动恢复
- **倍速播放**：0.1 ~ 4.0（预设 0.5/0.75/1/1.25/1.5/1.75/2/2.5/3/4 + ±0.1 微调），全局记忆
- **播放模式**：顺序 / 列表循环 / 单曲循环 / 随机
- **字幕**：同名 `.vtt` 自动挂载，一键开关；悬浮展示，开关不挤压版面；播放中途开启即时跟词
- **其他**：±15s 快进退、定时停止（5~60 分钟）、键盘快捷键（空格 / ←→ / ↑↓）、深色模式自适应
- **Mac 风格 UI**：毛玻璃窗口、交通灯、60s/圈慢速黑胶唱片、移动端自适应（≤899px 整页滚动，滚过播放器后顶部吸附迷你控制条：播放/切集/搜索/倍速）

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
```

打开 <http://127.0.0.1:8792>（端口可在 `.env` 改 `KAUDIO_PORT`）。手机同局域网访问 `http://<电脑IP>:8792`。

### Docker 方式（可选）

不想配 Python 环境时，用 Docker 一键起（镜像内已含 ffmpeg，ffprobe 自动可用）：

```bash
docker compose up -d --build
```

- 首次构建后访问 <http://127.0.0.1:8792>，与本地方式完全一致
- **音频目录挂载**：默认挂 `./audio`；在 `.env` 里设 `AUDIO_DIR` 可挂任意宿主机目录：

  ```bash
  # .env
  AUDIO_DIR=F:/music        # Windows 示例（macOS/Linux: /path/to/music）
  KAUDIO_PORT=8792          # 宿主机端口，可改
  ```

  再执行 `docker compose up -d` 生效。
- **前端热改**：`static/` 目录以挂卷方式覆盖进容器，改 HTML/CSS/JS 无需 rebuild，刷新页面即可
- 时长缓存落在 `./.cache/docker`（可由 `CACHE_DIR` 改），删掉即重新探测
- 健康检查内置（`/api/list` 30s 一次），`docker ps` 可见 healthy 状态；`restart: unless-stopped` 开机自启随 Docker
- 常用命令：

  ```bash
  docker compose logs -f          # 看日志
  docker compose restart          # 重启
  docker compose down             # 停止
  ```

> Docker 方式下 `.env` 中的路径只影响宿主机侧挂载源；容器内路径固定为 `/app/audio`、`/app/.cache`，无需关心。

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
