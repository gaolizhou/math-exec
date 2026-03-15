FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=6000 \
    GUNICORN_WORKERS=2 \
    SAVED_PRESETS_FILE=/app/data/saved_presets.json \
    PDF_CJK_FONT_PATH=/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc \
    PDF_CJK_SUBFONT_INDEX=2

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-noto-cjk fontconfig \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

COPY . .

RUN mkdir -p /app/data \
    && if [ -f /app/saved_presets.json ]; then cp /app/saved_presets.json /app/data/saved_presets.json; fi

EXPOSE 6000

CMD ["sh", "-c", "gunicorn -w ${GUNICORN_WORKERS:-2} -b 0.0.0.0:${PORT:-6000} app:app"]
