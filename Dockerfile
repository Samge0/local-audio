# ---- 系统依赖层（极少变化，放最前最大化缓存命中）----
FROM python:3.13-slim AS system-deps
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# ---- Python 依赖层（仅 requirements.txt 变化时重建）----
FROM python:3.13-slim AS deps
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --timeout 120 \
    -r /tmp/requirements.txt && rm /tmp/requirements.txt

# ---- 运行层：继承系统依赖，再叠加 Python 依赖 ----
FROM system-deps
COPY --from=deps /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages

WORKDIR /app
COPY config.py server.py ./
COPY static/ ./static/

# 音频目录（挂卷覆盖）
RUN mkdir -p /app/audio /app/.cache
VOLUME ["/app/audio"]

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AUDIO_DIR=/app/audio \
    CACHE_DIR=/app/.cache \
    KAUDIO_PORT=8792

EXPOSE 8792

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8792/api/list',timeout=4)" || exit 1

CMD ["python", "server.py"]
