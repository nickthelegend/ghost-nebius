FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir numpy scipy httpx

COPY hub ./hub
COPY demo ./demo
COPY web/dist ./web/dist
RUN useradd --system --uid 10001 --home /app ghost \
    && mkdir -p /app/data \
    && chown ghost:ghost /app/data

USER ghost
EXPOSE 8780
CMD ["python", "-m", "hub.server", "--host", "0.0.0.0"]
