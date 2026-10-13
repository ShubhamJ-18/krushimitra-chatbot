# 🌾 KrushiMitra AI (कृषीमित्र AI) — Advanced Farmer Assistant & Agricultural Knowledge Engine

KrushiMitra AI is a secure, multilingual agricultural advisor engineered specifically for Indian farmers. It combines real-time conversational intelligence, verified retrieval-augmented generation (RAG) from ICAR and State Agricultural Universities, AI vision plant pathology, live weather and agromet spray advisories, official APMC mandi wholesale rates, and government scheme eligibility assessments.

---

## 🌟 Key Highlights & Architecture

- **Brand & Identity**: Modern, accessible, farmer-first interface preserving green agricultural aesthetics with high contrast, large touch targets, and mobile responsiveness.
- **Multilingual Excellence**: Native support and prioritization for **Marathi (`mr-IN`)**, **Hindi (`hi-IN`)**, and **English (`en-IN`)**, with additional regional language support (Punjabi, Tamil, Telugu, Kannada, Bengali, Gujarati, Urdu, Spanish, French).
- **Backend Architecture**: Clean, production-ready **FastAPI** backend with SQLite database, full-text search (FTS5) for RAG, Pydantic v2 schemas, and CORS security.
- **Security & Privacy**: Zero hardcoded API keys. All keys configured via `.env`. Farmer profile stored securely with explicit consent.
- **Agricultural RAG Pipeline**: Cites official advisories from:
  - **ICAR** (Central Institute for Cotton Research, Indian Institute of Soybean Research, DOGR Onion/Garlic)
  - **State Agricultural Universities**: MPKV Rahuri, Dr. PDKV Akola, VNMKV Parbhani, BSKKV Dapoli
  - **KVKs**: Krishi Vigyan Kendra Baramati and regional centres
  - **IMD Pune**: Agricultural Meteorology Division
  - **Government Portals**: Ministry of Agriculture & Farmers Welfare, GoI & MahaDBT

---

## 🛠️ Implemented Agricultural Modules

| Module | Features & Capabilities |
| :--- | :--- |
| **💬 Chat Advisor** | Contextual conversation memory across turns, intent detection, evidence-backed advice with numbered steps, explanation of *why* steps work, and clickable source citations. |
| **🩺 Crop Doctor** | **Voice-First & Picture-Based consultation experience designed for farmers with limited literacy.** Replaced complex 6-field forms with a 3-choice home screen (📸 Photo, 🎤 Voice in Marathi/Hindi/English, 👆 Picture Problem Cards), picture crop selector (Cotton, Soybean, Tomato, Onion, etc.), single non-intrusive follow-up question evaluation, and a 5-card visual diagnosis screen with Web Speech API audio narration and toll-free Kisan Call Center (1800-180-1551) integration. |
| **🔬 AI Crop Vision** | Multi-image leaf/pest upload and analysis using vision AI. Detects foliar lesions, chlorosis, and pest signs; returns organic remedies, certified chemical dosages with pre-harvest intervals, and expert escalation warnings. |
| **🧪 Fertilizer Advisor** | Balanced nutrient calculator combining Farm Yard Manure (FYM), vermicompost, biofertilizers (Rhizobium, PSB, Azotobacter), and stage-specific chemical NPK based on university guidelines. |
| **💧 Irrigation Advisor** | Soil-specific water budgeting (Heavy black clay vs loam vs sandy). In-line drip scheduling and hydrochloric acid (HCl) flushing instructions for hard water dripper scaling. |
| **🌤️ Live Weather & Agromet** | Real-time temperature, humidity, wind speed, and precipitation via Open-Meteo. Automatically generates **Spraying Safety Window**, **Irrigation Need**, and **IMD Agromet alerts**. |
| **🏪 Mandi Market Prices** | Observed APMC wholesale rates from Agmarknet and MSAMB (Lasalgaon Onion, Latur Soybean, Yavatmal Cotton, Narayangaon Tomato, Akola Tur, etc.) with arrival quantities and price trends. |
| **🏛️ Government Schemes** | Comprehensive guides for PM-KISAN & Namo Shetkari (₹12,000/yr), PM Fasal Bima Yojana (₹1 Crop Insurance), MahaDBT Equipment/Drip Subsidies, and KCC. Includes an interactive **Eligibility Assessment Quiz**. |
| **🗺️ Crop Planning Assistant** | Agro-ecological seasonal crop rotations (Kharif, Rabi, Zaid) comparing water requirements, soil depth suitability, and economic trade-offs. |
| **🎤 Multilingual Voice** | Speech-to-Text (STT) with active recording pulse and Text-to-Speech (TTS) reading advice aloud in Marathi, Hindi, and English with stop/play controls. |

---

## 📂 Project Structure

```
s:/project/chatbot/
├── app/
│   ├── __init__.py
│   ├── main.py                     # FastAPI app, lifespan setup, middleware, static routes
│   ├── config.py                   # Pydantic Settings and .env reader
│   ├── database.py                 # SQLite connection and FTS5 virtual table setup
│   ├── models/
│   │   ├── __init__.py
│   │   └── conversation.py         # SQLAlchemy models (Conversation, Message, FarmerProfile, Feedback)
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── schemas.py              # Pydantic request & response validation schemas
│   ├── services/
│   │   ├── ai_service.py           # Conversational AI, intent detection, context memory & RAG prompt
│   │   ├── rag_service.py          # SQLite FTS5 BM25 search & knowledge ingestion engine
│   │   ├── vision_service.py       # Plant pathology image analyzer with format/size validation
│   │   ├── crop_doctor.py          # Guided 7-step diagnostic flow & missing parameters detector
│   │   ├── weather_service.py      # Open-Meteo live API integration & IMD Agromet advisory rules
│   │   ├── mandi_service.py        # APMC market rates service (Agmarknet & MSAMB data)
│   │   └── scheme_service.py       # Verified government schemes & eligibility evaluator
│   └── api/
│       ├── chat.py                 # POST /api/chat, GET/DELETE /api/conversations
│       ├── crop_analysis.py        # POST /api/analyze-crop
│       ├── weather.py              # GET /api/weather
│       ├── market_prices.py        # GET /api/market-prices
│       ├── schemes.py              # GET /api/schemes, POST /api/schemes/check
│       ├── feedback.py             # POST /api/feedback
│       ├── profile.py              # GET/PUT /api/profile
│       └── health.py               # GET /api/health
├── data/
│   ├── knowledge_base/             # Approved ICAR/KVK/SAU JSON documents
│   │   ├── cotton_pink_bollworm.json
│   │   ├── soybean_disease.json
│   │   ├── onion_thrips_blotch.json
│   │   ├── soil_fertility.json
│   │   ├── drip_irrigation.json
│   │   ├── government_schemes.json
│   │   ├── crop_planning.json
│   │   └── tomato_weather_advisory.json
│   └── mandi_cache.json            # Official APMC market benchmark records
├── scripts/
│   ├── init_db.py                  # Database and FTS5 index initialization script
│   └── ingest_knowledge.py         # Knowledge document indexing script
├── tests/
│   └── test_krushimitra.py         # Automated pytest test suite (11 test cases)
├── .env.example                    # Environment variable configuration template
├── .env                            # Local configuration file (git-ignored)
├── .gitignore                      # Git ignore patterns
├── requirements.txt                # Python package dependencies
├── run.py                          # Application runner
├── Chatbot.html                    # Modernized frontend application
└── Chatbot(1).html                 # Synchronized copy of frontend application
```

---

## 🚀 Installation & Quick Start

### 1. Prerequisites
- Python 3.10+ (Tested on Python 3.14)
- Web browser (Chrome, Edge, or modern browser for Speech APIs)

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables
Copy `.env.example` to `.env` and verify your configuration:
```bash
cp .env.example .env
```
Default keys for Groq LLM are pre-configured in `.env`. You can also configure Google Gemini or OpenAI keys if desired.

### 4. Initialize Database and Knowledge Base
```bash
python scripts/init_db.py
```
This initializes the SQLite database schema and indexes all verified agricultural documents into SQLite FTS5.

### 5. Start the Server
```bash
python run.py
```
Or with uvicorn directly:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 6. Open the Application
Open your browser and navigate to:
- **Web App**: [http://localhost:8000](http://localhost:8000)
- **Interactive Swagger API Docs**: [http://localhost:8000/api/docs](http://localhost:8000/api/docs)
- **ReDoc Documentation**: [http://localhost:8000/api/redoc](http://localhost:8000/api/redoc)

---

## 🗄️ Database Configuration & Vercel Deployment

KrushiMitra AI supports both **PostgreSQL** (production & serverless) and **SQLite** (local testing & development).

### 1. Root Cause of `sqlite3.OperationalError: unable to open database file` on Vercel
Vercel serverless functions run in a stateless, read-only filesystem environment (only `/tmp` is temporarily writable and is wiped between invocations). When an application attempts to write to a local SQLite database (such as `./data/krushimitra.db`) on Vercel, SQLite fails with:
```text
sqlite3.OperationalError: unable to open database file
```
**Fix:** The application uses hosted PostgreSQL in production via the `DATABASE_URL` environment variable, while preserving SQLite for local offline development.

### 2. Configuring `DATABASE_URL` on Vercel
1. Create a free hosted PostgreSQL database on any provider, such as:
   - **Neon**: [neon.tech](https://neon.tech) (Serverless PostgreSQL)
   - **Supabase**: [supabase.com](https://supabase.com)
   - **Render**: [render.com](https://render.com)
   - **Railway**: [railway.app](https://railway.app)
   - **AWS RDS** / **Google Cloud SQL**
2. In your **Vercel Dashboard**:
   - Go to your Project -> **Settings** -> **Environment Variables**.
   - Add Key: `DATABASE_URL`
   - Add Value: your PostgreSQL connection string, e.g.:
     ```text
     postgresql://username:password@ep-sample-pooler.us-east-2.aws.neon.tech/neondb?sslmode=require
     ```
   - Ensure the variable is enabled for **Production**, **Preview**, and **Development**.
3. **Automatic URL Normalization:**
   Hosted providers often prefix URLs with `postgres://` instead of `postgresql://`. The application automatically detects and normalizes `postgres://` to `postgresql://` so SQLAlchemy and `psycopg2-binary` connect smoothly without manual edits.
4. **Safe Schema Initialization:**
   On startup, `Base.metadata.create_all()` safely creates any missing tables (`conversations`, `messages`, `farmer_profiles`, `feedbacks`, `rag_documents`) without dropping or erasing existing farmer data. Verified RAG advisories are automatically ingested on first boot.

### 3. Configuring `DATABASE_URL` Locally
In your local `.env` file:
- **For SQLite (Default)**:
  ```env
  DATABASE_URL=sqlite:///./data/krushimitra.db
  ```
- **For Local or Remote PostgreSQL**:
  ```env
  DATABASE_URL=postgresql://postgres:yourpassword@localhost:5432/krushimitra
  ```

---

## 📚 Adding New Documents to Knowledge Base (RAG)

1. Create a new JSON file inside `data/knowledge_base/` following this structure:
```json
{
  "id": "KB-CROP-009",
  "title": "Document Title",
  "topic": "Pest Management / Agronomy",
  "crop": "Crop Name",
  "region": "State / District",
  "language": "mr, hi, en",
  "source_name": "Official Institution Name (e.g. MPKV Rahuri / ICAR)",
  "source_url": "https://official-portal-url.gov.in",
  "publication_date": "YYYY-MM-DD",
  "summary": "Short 1-2 sentence summary of findings.",
  "content": "Detailed management, dosage, safety precautions, and biological controls."
}
```
2. Run the ingestion script:
```bash
python scripts/ingest_knowledge.py
```
The document is indexed into SQLite FTS5 with BM25 ranking and immediately available for citation by the AI assistant.

---

## 🧪 Automated Testing

Run the test suite with `pytest`:
```bash
python -m pytest tests/test_krushimitra.py -v
```

The test suite validates:
1. `test_health_endpoint`: Backend status and FTS5 document count.
2. `test_rag_retrieval_and_citation`: Authentic source retrieval with URLs and dates.
3. `test_crop_doctor_missing_information_detection`: Detecting missing crop parameters and generating targeted follow-up questions.
4. `test_chat_api_marathi_yellow_leaves`: Marathi response quality and source attribution.
5. `test_chat_api_hindi_irrigation`: Hindi irrigation advice.
6. `test_chat_api_english_disease_and_context_memory`: Multi-turn context memory across consecutive questions.
7. `test_weather_endpoint`: Open-Meteo data parsing and IMD agromet alerts.
8. `test_mandi_prices_endpoint`: Mandi rate retrieval and commodity filtering.
9. `test_schemes_and_eligibility`: Scheme guidelines and interactive eligibility evaluation.
10. `test_crop_analysis_validation_invalid_file`: Image format/size validation.
11. `test_conversation_deletion`: Conversation creation and cascading deletion.
12. `test_simplified_crop_doctor_marathi_voice`: Voice-driven consultation in Marathi with automatic Cotton detection and audio narration.
13. `test_simplified_crop_doctor_hindi_problem_card`: Picture-based problem card consultation in Hindi with bollworm advisory.
14. `test_crop_doctor_single_followup_question`: Verification that only ONE non-intrusive multiple-choice question is evaluated.
15. `test_crop_doctor_consultation_no_mandatory_fields`: Accessibility guarantee that queries without mandatory crop/district fields succeed gracefully.

---

## 🔑 External APIs & Credentials Summary

| Service | Provider | Status / Credentials | Fallback Behavior |
| :--- | :--- | :--- | :--- |
| **Conversational LLM** | Groq (`llama-3.3-70b-versatile`) | `GROQ_API_KEY` in `.env` | Heuristic agricultural expert engine using RAG documents. Never crashes. |
| **Vision AI** | Groq (`meta-llama/llama-4-scout-17b-16e-instruct`) | `GROQ_API_KEY` in `.env` | Transparent service message guiding farmer to Crop Doctor consultation. |
| **Weather & Agromet** | Open-Meteo & IMD Agromet Rules | Free (No API key required) | IMD seasonal guidelines with local sky observation advice. |
| **Mandi Market Prices** | Agmarknet & MSAMB | Cached official APMC records | Displays historical market benchmark with disclaimer. |
| **Voice STT & TTS** | Web Speech API | Browser-native (No external key needed) | Graceful text fallback with visual notification. |

---

## 📋 Implemented vs. Remaining Limitations

### Implemented Features:
- Secure backend API with FastAPI, Pydantic v2 validation, SQLite FTS5 RAG.
- Full context memory across conversation turns without repeating information.
- Guided 7-step Crop Doctor diagnostic consultation.
- Real Vision AI leaf pathology analysis with image type/size validation.
- Live weather integration with spraying safety windows and irrigation advice.
- APMC mandi prices with commodity and district search.
- Verified government schemes with interactive eligibility evaluator.
- Speech-to-Text and Text-to-Speech in Marathi, Hindi, and English.
- Conversation persistence in SQLite with deletion capability.
- Farmer profile configuration modal.
- Zero hardcoded keys in frontend code.

### Operational Limitations:
- **Live Mandi Rates**: Agmarknet portal rates reflect reported wholesale arrivals up to the latest reporting date; intraday auction fluctuations are not streamed tick-by-tick.
- **Microphone Access**: Speech recognition requires browser permission and HTTPS or localhost access.
- **Offline Vision AI**: Local offline image pathology model inference requires a local GPU; in offline mode, farmers are directed to use the textual Crop Doctor consultation flow.
