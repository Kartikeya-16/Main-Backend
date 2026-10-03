FROM python:3.12-slim

WORKDIR /app



# Install system build dependencies required for compiling IndicTransToolkit and tokenizers
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install lightweight CPU-only PyTorch first (~180MB instead of 2.8GB CUDA package)
RUN pip install --no-cache-dir torch --extra-index-url https://download.pytorch.org/whl/cpu

# Copy requirements and install remaining dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy microservice codebase
COPY . .

EXPOSE 8002

# Run FastAPI app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]
