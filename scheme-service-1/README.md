# Scheme Generator Microservice (scheme-service-1)

A standalone FastAPI microservice for the **ArthSaathi** monorepo that recommends matching Indian Government Schemes based on user demographic and socio-economic profiles.

---

## Service Overview

The Government Scheme Generator microservice takes a user's multi-step onboarding profile (gender, age, state, residence, caste category, disability, minority status, student status, BPL status, and annual income) and matches it against an enriched dataset of ~4,857 government schemes (`data/finpilot_schemes_enriched.csv`).

### Key Features
- **In-memory data architecture**: Pre-parses JSON string columns (`eligibility_caste`, `eligibility_caste_extended`, `eligibility_state`) at startup using pandas and `@lru_cache` for zero-latency request matching.
- **Rule-based matching engine**: Combines structured hard filtering, soft scoring boosts, and confidence categorization.
- **Port Allocation**: Runs on **Port 8003** (Port 8000: `finpilot-backend`, Port 8001: `ml-service-1`, Port 8002: `ml-service-2-translation`, Port 8003: `scheme-service-1`).

---

## Technical Setup & Execution

### 1. Installation
Ensure virtual environment is active and dependencies are installed:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Dataset Placement
Place `finpilot_schemes_enriched.csv` inside `scheme-service-1/data/`:
```text
scheme-service-1/data/finpilot_schemes_enriched.csv
```

### 3. Run Microservice
Start the FastAPI server using Uvicorn on Port 8003:

```bash
uvicorn app.main:app --reload --port 8003
```

### 4. Run Test Suite
Run the unit test suite using `pytest`:

```bash
pytest
```

---

## Architectural & Design Rationale (Viva Defense Notes)

### 1. Dual-Tier Matching Design: Hard Filters vs. Soft Boosts
- **Hard Filters**: Applied ONLY when `has_structured_eligibility` is `True`. Enforces strict exclusions on criteria such as age limits, residence type, state restrictions, caste eligibility, income caps, disability, and BPL requirements.
- **Soft Boosts**: Additive scoring (+15 minority status, +15 student status, +10 category relevance) to reward strong context alignment without penalizing users when data fields are incomplete or non-exclusive.

### 2. Handling Unstructured Eligibility (`has_structured_eligibility = False`)
- **Rationale**: Approximately ~50% of scraped scheme records lack complete structured eligibility parameters. Silently dropping or hard-filtering these records would result in massive **false negatives**, hiding relevant government schemes from users.
- **Solution**: For records where `has_structured_eligibility` is `False`, hard filters are skipped entirely. The scheme remains eligible and receives a base score of 50, but its `match_confidence` is capped at `"medium"` (or `"low"` if purely keyword-matched). This guarantees recall while clearly signaling confidence levels to the frontend interface.

### 3. Gender Data Limitation Handling
- The dataset currently contains structured values for `"male"`, `"female"`, and `"all"`. For users identifying as `"transgender"`, gender hard filters are bypassed (`"all"` match treatment) to avoid discriminatory false exclusions caused by dataset schema limitations.

---

## API Endpoints

- **`GET /health`**: Returns service status and count of schemes loaded in memory (`schemes_loaded`).
- **`POST /schemes/match`**: Accepts `UserProfile` payload and optional `limit` query param, returning ranked `MatchedScheme` items.
- **`GET /schemes/{slug}`**: Returns full metadata for a single scheme given its unique `slug`.
