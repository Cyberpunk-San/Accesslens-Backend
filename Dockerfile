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
ENV APP_HOME=/app
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONPATH=$APP_HOME

WORKDIR $APP_HOME

# Copy virtualenv from builder
COPY --from=builder /opt/venv /opt/venv

# Install chromium (Playwright specific)
RUN playwright install --with-deps chromium

# Copy application code
COPY . .

RUN mkdir -p data models logs

EXPOSE 8000

COPY scripts/docker-entrypoint.sh /usr/local/bin/
RUN sed -i 's/\r$//' /usr/local/bin/docker-entrypoint.sh && \
    chmod +x /usr/local/bin/docker-entrypoint.sh

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]