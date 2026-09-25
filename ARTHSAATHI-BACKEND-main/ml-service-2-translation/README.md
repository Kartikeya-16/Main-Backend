# IndicTrans2 Translation Microservice

A self-contained, offline language-translation microservice for the **ArthSaathi** project. It uses AI4Bharat's MIT-licensed `IndicTrans2` distilled models to translate text between English and the 22 scheduled Indian languages, completely running on local weights without any external API calls.

## Tech Stack & Models

- **Framework**: FastAPI (Python)
- **Model Framework**: Hugging Face Transformers & PyTorch
- **Models**:
  - `ai4bharat/indictrans2-en-indic-dist-200M` (English → Indic)
  - `ai4bharat/indictrans2-indic-en-dist-200M` (Indic → English)
  - `ai4bharat/indictrans2-indic-indic-dist-320M` (Indic ↔ Indic)
- **Language Codes**: FLORES-200 style (e.g. `eng_Latn`, `hin_Deva`, `tam_Taml`, etc.)

---

## Directory Structure

```text
ml-service-2-translation/
├── app/
│   ├── __init__.py
│   ├── languages.py    # Language map & routing logic
│   ├── main.py         # FastAPI app config and endpoints
│   ├── model.py        # Lazy loading TranslationEngine
│   └── schemas.py      # Request & response Pydantic models
├── tests/
│   └── test_translate.py
├── .env.example
├── Dockerfile
├── download_models.py  # Weights preloader
└── requirements.txt
```

---

## Setup & Running Locally

### 1. Installation
Create a virtual environment and install the required dependencies:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Pre-download Model Weights
Download the model weights locally so the service can run completely offline:

```bash
python download_models.py
```

### 3. Run the Microservice
Start the FastAPI server using Uvicorn:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload
```

---

## Running with Docker

You can build and package the service in a Docker container. The build process runs `download_models.py` internally, making the image fully self-contained.

```bash
# Build the Docker image (automatically caches ~2GB of weights)
docker build -t arthsaathi-translation-service .

# Run the container
docker run -d -p 8002:8002 --name translation-service arthsaathi-translation-service
```

---

## API Endpoints

### 1. Translate Single Sentence
* **Endpoint**: `POST /translate`
* **Request Body**:
```json
{
  "text": "Hello, how can I help you today?",
  "src_lang": "eng_Latn",
  "tgt_lang": "hin_Deva"
}
```
* **Response**:
```json
{
  "translated_text": "नमस्ते, मैं आज आपकी क्या मदद कर सकता हूँ?",
  "src_lang": "eng_Latn",
  "tgt_lang": "hin_Deva"
}
```

### 2. Translate Batch of Sentences
* **Endpoint**: `POST /translate/batch`
* **Request Body**:
```json
{
  "texts": [
    "Welcome to ArthSaathi.",
    "Your financial security is our priority."
  ],
  "src_lang": "eng_Latn",
  "tgt_lang": "hin_Deva"
}
```
* **Response**:
```json
{
  "translated_texts": [
    "अर्थसाथी में आपका स्वागत है।",
    "आपकी वित्तीय सुरक्षा हमारी प्राथमिकता है।"
  ],
  "src_lang": "eng_Latn",
  "tgt_lang": "hin_Deva"
}
```

### 3. Get Supported Languages
* **Endpoint**: `GET /languages`
* **Response**:
```json
{
  "eng_Latn": "English",
  "hin_Deva": "Hindi",
  "tam_Taml": "Tamil",
  ...
}
```

### 4. Health Check
* **Endpoint**: `GET /health`
* **Response**:
```json
{
  "status": "ok",
  "device": "cpu",
  "loaded_models": {
    "en-indic": true,
    "indic-en": false,
    "indic-indic": false
  },
  "model_version": "200M/320M dist"
}
```
