# Hugging Face Docker Space. Build from the repository root:
#   docker build -f globe/Dockerfile -t sars-globe-api .
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY drought_monitor ./drought_monitor
COPY globe ./globe

ENV PORT=7860
ENV CORS_ORIGINS=*
EXPOSE 7860

CMD ["sh", "-c", "uvicorn globe.api.main:app --host 0.0.0.0 --port ${PORT}"]
