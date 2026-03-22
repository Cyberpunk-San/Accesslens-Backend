# Stage 1: Build dependencies
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    python3-venv \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install dependencies using CPU-only index for all Torch-related packages
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --no-cache-dir --prefer-binary \
    --timeout 1000 \
    --extra-index-url https://download.pytorch.org/whl/cpu \
    torch torchvision torchaudio transformers accelerate sentencepiece Pillow numpy \
    -r requirements.txt

# Stage 2: Runtime
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV APP_HOME=/home/user/app
ENV PATH="/home/user/.local/bin:/opt/venv/bin:$PATH"
ENV PYTHONPATH=$APP_HOME

# Set up a new user with UID 1000 (Hugging Face requirement)
RUN id -u 1000 >/dev/null 2>&1 || useradd -m -u 1000 user
WORKDIR /home/user/app

# Copy virtualenv from builder
COPY --from=builder /opt/venv /opt/venv

# Install chromium (Playwright specific) - must be root
RUN playwright install --with-deps chromium

# Prepare application directories and set permissions
RUN mkdir -p data models logs
COPY --chown=1000:1000 . .
RUN chown -R 1000:1000 /home/user/app

# Set up entrypoint - as root
COPY scripts/docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

EXPOSE 7860

# Finally switch to the non-root user
USER 1000

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]