FROM python:3.12-slim

WORKDIR /app



# Install system build dependencies required for compiling IndicTransToolkit and tokenizers
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy microservice codebase
COPY . .

# Run pre-download script during container build to cache models locally in the image (or download on demand)
RUN python download_models.py || true

EXPOSE 8002

# Run FastAPI app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]
