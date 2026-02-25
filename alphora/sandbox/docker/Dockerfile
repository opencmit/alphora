# 基础镜像
FROM python:3.11-slim AS base

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    WORKSPACE_DIR=/mnt/workspace \
    SKILLS_DIR=/mnt/skills \
    OUTPUT_DIR=/output \
    SANDBOX_USER=sandbox \
    SANDBOX_UID=1000 \
    SANDBOX_GID=1000

# 全局配置清华源
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# 设置工作目录
WORKDIR /app

COPY requirements-runtime.txt .

RUN pip install --no-cache-dir -r requirements-runtime.txt

# Mount-point directories (created at build time, populated at runtime via bind mounts)
RUN mkdir -p /mnt/workspace /mnt/skills

WORKDIR /mnt/workspace

COPY . .
