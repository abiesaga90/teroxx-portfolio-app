FROM python:3.12-slim AS base

# System libraries required by WeasyPrint to render the branded proposal PDF.
# pango + cairo + fontconfig + harfbuzz handle text shaping, vector layout, and
# embedded @font-face WOFF/OTF loading. shared-mime-info silences a runtime
# warning on first PDF render.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libpangocairo-1.0-0 \
        libcairo2 \
        libharfbuzz0b \
        libffi8 \
        fonts-dejavu-core \
        fontconfig \
        shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
