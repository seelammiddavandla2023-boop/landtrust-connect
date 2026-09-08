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
RUN mkdir -p /app/data

WORKDIR /app/backend

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    EXTRACTION_MODE=DEMO

# Set to 1 to include the OCR arm of the evaluation in the image. It rasterises every
# page and runs Tesseract over it, which takes several minutes on a small build machine
# — worth it when the deployed Research Results page is the thing being presented,
# not worth it on an ordinary deploy. CI runs the OCR arm on every push regardless, so
# the figure is verified continuously whether or not it is baked in here.
ARG EVAL_OCR=0

# Build the demonstration state into the image rather than at boot.
#
#  1. Render the synthetic corpus (deterministic, ~3 s).
#  2. Run the evaluation against a THROWAWAY database. The harness asks the assistant
#     questions and recomputes risk, which writes rows; letting it touch the database
#     the demo will serve would mean the reviewer sees a file the evaluation had
#     already poked at. Only data/metrics.json survives this step.
#  3. Seed the database the application actually serves, from scratch.
#
# The upshot: a cold start finds a populated database and an evaluation already run, so
# it boots in seconds and /research shows real computed numbers instead of its empty
# state. Without a mounted disk the container's copy is reset on each restart, which is
# what the demonstration wants anyway — it always begins from the same known state.
RUN set -eux; \
    python -m app.seed.generate; \
    EVAL_DB="sqlite:////tmp/eval.db"; \
    DATABASE_URL="$EVAL_DB" python -m app.seed.seed --reset; \
    if [ "$EVAL_OCR" = "1" ]; then \
        DATABASE_URL="$EVAL_DB" python -m app.eval.run_eval --ocr; \
    else \
        DATABASE_URL="$EVAL_DB" python -m app.eval.run_eval; \
    fi; \
    rm -f /tmp/eval.db; \
    python -m app.seed.seed --reset; \
    test -s /app/data/metrics.json; \
    test -s /app/data/landtrust.db

EXPOSE 8000

# $PORT is injected by Render, Railway and Fly; 8000 is the local default.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
