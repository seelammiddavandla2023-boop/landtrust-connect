# LandTrust Connect API.
#
# Built from the repository root so the synthetic corpus generator and the data
# directory layout match what the application expects:
#     docker build -f backend/Dockerfile -t landtrust-api .
FROM python:3.11-slim

# tesseract-ocr enables the real-OCR path and the OCR arm of the evaluation harness.
# The prototype runs fully without it, falling back to text-layer extraction, so this
# line can be dropped if image size matters more than the OCR comparison.
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend ./backend
# The synthetic corpus and the database live here. On a host with a persistent disk,
# mount it at /app/data to keep uploads between restarts; without one the application
# regenerates the corpus and re-seeds on each cold start, which is the behaviour the
# demonstration wants anyway.
RUN mkdir -p /app/data

WORKDIR /app/backend
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    EXTRACTION_MODE=DEMO

EXPOSE 8000

# $PORT is injected by Render, Railway and Fly; 8000 is the local default.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
