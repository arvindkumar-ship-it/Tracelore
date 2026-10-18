FROM python:3.11-slim AS builder
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
WORKDIR /build
COPY requirements.lock /build/requirements.lock
RUN pip install --prefix=/install -r requirements.lock
COPY sdk/python /build/sdk/python
COPY backend /build/backend
RUN pip install --no-deps --prefix=/install /build/sdk/python /build/backend

FROM python:3.11-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN groupadd --system tracelore && useradd --system --gid tracelore --home /app tracelore
COPY --from=builder /install /usr/local
WORKDIR /app
COPY --chown=tracelore:tracelore backend backend
COPY --chown=tracelore:tracelore sdk/python/tracelore tracelore
COPY --chown=tracelore:tracelore bench bench
COPY --chown=tracelore:tracelore scripts scripts
RUN mkdir -p /app/artifacts /app/models /app/spool && chown -R tracelore:tracelore /app
USER tracelore
EXPOSE 8000 8001 9100 9101
ENTRYPOINT ["python", "-m", "backend.common.entrypoint"]
CMD ["api"]

FROM runtime AS ml
USER root
COPY requirements-ml.lock /tmp/requirements-ml.lock
RUN pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu -r /tmp/requirements-ml.lock
USER tracelore

FROM runtime AS inference
USER root
RUN pip install --no-cache-dir 'onnxruntime==1.31.0'
USER tracelore
