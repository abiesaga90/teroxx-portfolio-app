FROM python:3.12-slim AS base

# System libraries:
#  - pango/cairo/harfbuzz/fontconfig: SVG rasterisation (cairosvg) for the
#    proposal exhibits, plus text shaping.
#  - libreoffice-writer: converts the proposal .docx to PDF. The .docx is
#    the single source of truth; the PDF (and the Google Doc) are
#    conversions of it, so the three outputs cannot drift apart.
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
        libreoffice-writer \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Install the Teroxx brand fonts system-wide so LibreOffice renders the
# proposal PDF on-brand (Söhne / Sometimes Times), matching the .docx.
RUN mkdir -p /usr/share/fonts/teroxx \
    && cp app/static/fonts/*.otf /usr/share/fonts/teroxx/ \
    && fc-cache -f

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
