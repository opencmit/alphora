# 基础镜像
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
    PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn \
    WORKSPACE_DIR=/mnt/workspace \
    SKILLS_DIR=/mnt/skills \
    OUTPUT_DIR=/output \
    SANDBOX_USER=sandbox \
    SANDBOX_UID=1000 \
    SANDBOX_GID=1000

# 安装系统依赖 + Node.js
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl gcc g++ make cmake \
    libgomp1 libffi-dev \
    fonts-noto-cjk \
    sshpass openssh-client rsync wget git jq zip unzip \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && npm config set registry https://registry.npmmirror.com \
    && apt-get purge -y gcc g++ make cmake \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# Python venv
ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

WORKDIR /app
COPY requirements-runtime.txt .
RUN pip install --no-cache-dir -r requirements-runtime.txt

# Mount-point directories
RUN mkdir -p /mnt/workspace /mnt/workspace/uploads /mnt/workspace/outputs /mnt/skills

WORKDIR /mnt/workspace
COPY . .
