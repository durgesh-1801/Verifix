# ===========================================
# Verifix Production Dockerfile (Render)
# ===========================================
# Tesseract-only OCR mode for Free Tier (512MB RAM)
# PaddleOCR is excluded from requirements-prod.txt
# and disabled via ENABLE_PADDLEOCR=0

FROM python:3.11-slim

# Install system dependencies:
#   tesseract-ocr  — OCR engine (called via pytesseract subprocess)
#   libgl1         — OpenGL for OpenCV headless rendering
#   libglib2.0-0   — GLib for OpenCV/image processing
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       tesseract-ocr \
       tesseract-ocr-eng \
       libgl1 \
       libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies (production-only, no PaddleOCR)
COPY requirements-prod.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Production environment defaults
ENV ENABLE_PADDLEOCR=0
ENV FLASK_ENV=production
ENV LOG_LEVEL=INFO

# Expose Render's default port
EXPOSE 10000

# Run with single worker + extended timeout for Tesseract OCR processing
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:10000", "--workers", "1", "--timeout", "120"]
