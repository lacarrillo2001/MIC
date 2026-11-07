FROM node:22-bookworm-slim AS jsruntime
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir -r requirements.txt yt-dlp && useradd --create-home api
COPY --from=jsruntime /usr/local/bin/node /usr/local/bin/node
RUN pip install --no-cache-dir 'yt-dlp[default]==2026.10.26'
COPY shared shared
COPY config config
COPY sesiones sesiones
USER api
EXPOSE 8000
CMD ["uvicorn", "sesiones.app:app", "--host", "0.0.0.0", "--port", "8000"]
