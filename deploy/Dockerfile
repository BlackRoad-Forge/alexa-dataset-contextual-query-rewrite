# Multi-arch Docker image for the BlackRoad Stripe service.
# Supports both amd64 and arm64 (Raspberry Pi 4+).
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY stripe_service/ stripe_service/

EXPOSE 8000

CMD ["python", "-m", "stripe_service"]
