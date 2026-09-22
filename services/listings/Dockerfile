# Builder
FROM python:3.14.7-slim AS builder

WORKDIR /build
COPY services/listings/requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Runner
FROM python:3.14.7-slim

RUN groupadd -r appuser && \
    useradd -r -g appuser -d /app -s /sbin/nologin appuser

WORKDIR /app

COPY --from=builder /install /usr/local
COPY --chown=appuser:appuser shared/ /app/shared/
COPY --chown=appuser:appuser services/listings/ /app/

USER appuser

EXPOSE 8001

CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8001", \
     "--workers", "2", \
     "--proxy-headers", \
     "--no-server-header"]
