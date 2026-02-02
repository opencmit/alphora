# Base Image
FROM python:3.11-slim AS base

# Environment
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    WORKSPACE_DIR=/workspace \
    OUTPUT_DIR=/output \
    SANDBOX_USER=sandbox \
    SANDBOX_UID=1000 \
    SANDBOX_GID=1000

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    wget \
    git \
    unzip \
    build-essential \
    gcc \
    g++ \
    libffi-dev \
    libssl-dev \
    libpq-dev \
    libpng-dev \
    libjpeg-dev \
    libfreetype6-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -g ${SANDBOX_GID} ${SANDBOX_USER} \
    && useradd -m -u ${SANDBOX_UID} -g ${SANDBOX_GID} -s /bin/bash ${SANDBOX_USER}

# Create directories
RUN mkdir -p ${WORKSPACE_DIR} ${OUTPUT_DIR} \
    && chown -R ${SANDBOX_USER}:${SANDBOX_USER} ${WORKSPACE_DIR} ${OUTPUT_DIR}

# Install common Python packages
COPY docker/requirements-runtime.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

# Switch to non-root user
USER ${SANDBOX_USER}
WORKDIR ${WORKSPACE_DIR}

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "print('healthy')" || exit 1

CMD ["python", "-c", "print('Sandbox ready')"]


# Data Science Image
FROM base AS datascience

USER root

RUN apt-get update && apt-get install -y --no-install-recommends \
    libhdf5-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

USER ${SANDBOX_USER}

RUN pip install --no-cache-dir \
    numpy \
    pandas \
    scipy \
    scikit-learn \
    matplotlib \
    seaborn \
    plotly \
    statsmodels

# Machine Learning Image
FROM datascience AS ml

RUN pip install --no-cache-dir \
    torch --index-url https://download.pytorch.org/whl/cpu \
    torchvision --index-url https://download.pytorch.org/whl/cpu \
    transformers \
    datasets

# Minimal Image (Fast Startup)
FROM python:3.11-slim AS minimal

ENV PYTHONUNBUFFERED=1 \
    WORKSPACE_DIR=/workspace \
    SANDBOX_USER=sandbox \
    SANDBOX_UID=1000 \
    SANDBOX_GID=1000

RUN groupadd -g ${SANDBOX_GID} ${SANDBOX_USER} \
    && useradd -m -u ${SANDBOX_UID} -g ${SANDBOX_GID} -s /bin/bash ${SANDBOX_USER} \
    && mkdir -p ${WORKSPACE_DIR} \
    && chown -R ${SANDBOX_USER}:${SANDBOX_USER} ${WORKSPACE_DIR}

USER ${SANDBOX_USER}
WORKDIR ${WORKSPACE_DIR}

CMD ["python", "-c", "print('Minimal sandbox ready')"]
