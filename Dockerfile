# Stage 1 — builder: compile/install dependencies into an isolated virtualenv.
# Build tooling stays in this stage and never reaches the runtime image.
FROM python:3.12-alpine AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

# Toolchain + headers needed to build wheels on musl (aiokafka needs zlib, cffi needs libffi).
RUN apk add --no-cache build-base libffi-dev zlib-dev

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


# Stage 2 — runtime: minimal Alpine image, non-root, no build tooling.
FROM python:3.12-alpine AS runtime

LABEL org.opencontainers.image.title="IoT Device Simulator" \
      org.opencontainers.image.description="Configurable IoT device simulator with a real-time web UI and MQTT/Kafka/TCP/HTTP/AMQP/CoAP outputs plus optional AES-256-GCM payload encryption." \
      org.opencontainers.image.source="https://github.com/aparedero/iot-simulator" \
      org.opencontainers.image.licenses="MIT"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    LISTEN_HOST=0.0.0.0 \
    LISTEN_PORT=5050 \
    LOG_LEVEL=INFO

# Unprivileged user + the writable dir the optional file_output target uses.
RUN addgroup -g 10001 app \
    && adduser -D -u 10001 -G app -s /sbin/nologin app \
    && mkdir -p /app/output \
    && chown -R app:app /app

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY --chown=app:app app ./app
COPY --chown=app:app sample_data ./sample_data
COPY --chown=app:app examples ./examples

USER app

EXPOSE 8000 5050

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=2).status==200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
