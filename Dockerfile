FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared library
COPY shared/ ./shared/

# Copy the service code into the path the python scripts expect
RUN mkdir -p ./services/auth_service
COPY *.py ./services/auth_service/

CMD ["uvicorn", "services.auth_service.main:app", "--host", "0.0.0.0", "--port", "8002"]
