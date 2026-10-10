FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY data /app/data
COPY frontend /app/frontend
COPY services /app/services
COPY backend /app/backend

ENV SERVICE_MODULE="services.api_gateway.main:app"
ENV PORT="8000"

EXPOSE 8000 8001 8002 8003 8004 8005

CMD ["sh", "-c", "uvicorn ${SERVICE_MODULE} --host 0.0.0.0 --port ${PORT}"]
