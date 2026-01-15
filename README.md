# علوم القرآن | Quranic Sciences Platform

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)](https://www.docker.com/)

A comprehensive AI-powered platform for Quranic Sciences (علوم القرآن) featuring semantic search, comparative tafsir analysis, and the ten Quranic readings (القراءات العشر).

---

## Features

### Core Modules

| Module | Description |
|--------|-------------|
| **القراءات العشر** | Ten Quranic readings with differences, audio comparisons, and scholarly analysis |
| **التفاسير المقارنة** | Side-by-side comparison of 7+ classical tafsirs |
| **أسباب النزول** | Revelation contexts with sources and authentication |
| **البحث الدلالي** | AI-powered semantic search across 50,000+ vectors |

### AI Capabilities

- **Semantic Search**: Find verses by meaning, not just keywords
- **RAG-based Q&A**: Ask questions in Arabic, get answers with Quranic citations
- **Contextual Understanding**: Retrieves relevant tafsir, asbab, and related verses
- **Streaming Responses**: Real-time AI responses with source attribution

---

## Screenshots

### Quran Browser
![Quran Surah View](images/Quran_surah.png)

### القراءات العشر (Ten Readings)
![Qiraat Differences](images/Qiraat.png)

### التفاسير المقارنة (Comparative Tafsir)
![Tafsir Comparison](images/tafsir.png)

### أسباب النزول (Revelation Contexts)
![Asbab al-Nuzul](images/asbab_nzol.png)

### الإعراب (Grammatical Analysis)
![I'rab Analysis](images/eraab.png)

### AI Assistant
![AI Assistant](images/AI.png)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Client (Browser)                        │
└─────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FastAPI Application                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │   Web UI    │  │  REST API   │  │    AI Endpoints         │  │
│  │  (Jinja2)   │  │   /api/*    │  │  /api/ai/ask/stream     │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
          │                   │                    │
          ▼                   ▼                    ▼
┌──────────────────┐  ┌──────────────┐  ┌─────────────────────────┐
│    SQLite DB     │  │    Qdrant    │  │   OpenAI-Compatible     │
│  (280MB, local)  │  │ Vector Store │  │  - LLM (chat)           │
│                  │  │  50K vectors │  │  - Embeddings model     │
└──────────────────┘  └──────────────┘  └─────────────────────────┘
```

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Backend** | Python 3.10+, FastAPI, Uvicorn, Gunicorn |
| **Database** | SQLite (structured data), Qdrant (vectors) |
| **AI/ML** | OpenAI-compatible API (LLM + Embeddings) |
| **Frontend** | Jinja2 Templates, Bootstrap 5, Vanilla JS |
| **Deployment** | Docker, Cloud Run / Kubernetes |

---

## Quick Start

### Prerequisites

- Python 3.10+
- OpenAI-compatible API access (for AI features)

### Local Installation

```bash
# Clone the repository
git clone https://github.com/h9-tec/uloom-quran.git
cd uloom-quran

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Set environment variables
cp .env.example .env
# Edit .env with your Azure OpenAI credentials

# Initialize database (downloads and populates data)
python scripts/init_database.py

# Run the server
python run.py
```

Open http://localhost:8080 in your browser.

### Docker Deployment

```bash
# Build the image
docker build -t uloom-quran .

# Run with environment variables
docker run -p 8080:8080 \
  -e OPENAI_API_BASE=your-api-endpoint \
  -e OPENAI_API_KEY=your-key \
  -e QDRANT_URL=your-qdrant-url \
  uloom-quran
```

### Cloud Deployment

```bash
# Build and push to container registry
docker build -t uloom-quran .
docker tag uloom-quran your-registry/uloom-quran
docker push your-registry/uloom-quran

# Deploy with your preferred cloud provider
# (Cloud Run, Kubernetes, AWS ECS, etc.)
```

---

## Configuration

Create a `.env` file based on `.env.example`:

```bash
# Environment
ENV=production

# OpenAI-Compatible API (required for AI features)
OPENAI_API_BASE=https://api.openai.com/v1
OPENAI_API_KEY=your-api-key
CHAT_MODEL=gpt-4o
EMBEDDING_MODEL=text-embedding-ada-002

# Qdrant Vector Database
QDRANT_URL=http://localhost:6333

# Server
PORT=8080
```

---

## API Reference

### Quran Endpoints

```bash
# List all surahs
GET /api/quran/surahs

# Get surah details with verses
GET /api/quran/surah/{surah_id}

# Get specific verse
GET /api/quran/verse/{surah_id}/{ayah}

# Search verses
GET /api/quran/search?q=الرحمن
```

### Tafsir Endpoints

```bash
# Get all tafsirs for a verse
GET /api/tafsir/verse/{surah_id}/{ayah}

# Compare specific tafsirs
GET /api/tafsir/compare/{surah_id}/{ayah}?tafsirs=tabari,kathir,qurtubi
```

### Qiraat Endpoints

```bash
# Get qiraat differences for a verse
GET /api/qiraat/verse/{surah_id}/{ayah}

# Get all differences in a surah
GET /api/qiraat/surah/{surah_id}

# Search qiraat by keyword
GET /api/qiraat/search?q=إمالة
```

### AI Endpoints

```bash
# Semantic search (streaming)
GET /api/ai/ask/stream?q=ما معنى الصبر في القرآن

# AI health check
GET /api/ai/health
```

### Example Response

```json
{
  "type": "sources",
  "sources": [
    {
      "type": "verse",
      "reference": "2:153",
      "text": "يَا أَيُّهَا الَّذِينَ آمَنُوا اسْتَعِينُوا بِالصَّبْرِ وَالصَّلَاةِ",
      "score": 0.89
    }
  ]
}
```

---

## Database Schema

### Core Tables

| Table | Records | Description |
|-------|---------|-------------|
| `surahs` | 114 | Chapter metadata |
| `verses` | 6,236 | Uthmani text with keys |
| `tafsir_books` | 7 | Tafsir sources |
| `tafsir_entries` | 43,652 | Commentary per verse |
| `asbab_nuzul` | 677 | Revelation contexts |
| `qurra` | 10 | Ten readers |
| `ruwat` | 20 | Twenty transmitters |
| `qiraat_variants` | 1,500+ | Reading differences |

### Vector Collections (Qdrant)

| Collection | Vectors | Description |
|------------|---------|-------------|
| `quran_verses` | 6,236 | Verse embeddings |
| `tafsir_texts` | 43,652 | Tafsir embeddings |
| `asbab_nuzul` | 677 | Asbab embeddings |
| **Total** | **50,565** | Semantic search index |

---

## Available Tafsirs

| Tafsir | Author | Era |
|--------|--------|-----|
| جامع البيان | الإمام الطبري | 310 هـ |
| تفسير القرآن العظيم | الإمام ابن كثير | 774 هـ |
| معالم التنزيل | الإمام البغوي | 516 هـ |
| الجامع لأحكام القرآن | الإمام القرطبي | 671 هـ |
| تيسير الكريم الرحمن | الشيخ السعدي | 1376 هـ |
| التحرير والتنوير | الشيخ ابن عاشور | 1393 هـ |
| الوسيط | الشيخ طنطاوي | 1431 هـ |

---

## Project Structure

```
uloom-quran/
├── src/
│   ├── api/                 # FastAPI application
│   │   ├── main.py          # App entry point
│   │   └── routes/          # API endpoints
│   ├── ai/                  # AI services
│   │   ├── config.py        # LLM & embedding config
│   │   └── services/        # RAG, embeddings, Qdrant
│   ├── scrapers/            # Data collection scripts
│   └── services/            # Business logic
├── templates/               # Jinja2 HTML templates
├── static/                  # CSS, JS assets
├── scripts/                 # Database & indexing scripts
├── db/                      # SQLite database & schemas
├── k8s/                     # Kubernetes manifests
├── Dockerfile               # Container definition
├── requirements.txt         # Python dependencies
└── .env.example             # Environment template
```

---

## Data Sources & Attribution

| Source | Content | License |
|--------|---------|---------|
| [Quran-Data](https://github.com/rn0x/Quran-Data) | Quran JSON with metadata | MIT |
| [tafseer-sqlite-db](https://github.com/Mr-DDDAlKilanny/tafseer-sqlite-db) | Arabic tafsirs | Open |
| [tafsir_api](https://github.com/spa5k/tafsir_api) | Additional tafsirs | MIT |
| [nquran.com](https://www.nquran.com/) | القراءات العشر | Educational |

---

## Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Setup

```bash
# Install dev dependencies
pip install -r requirements.txt

# Run with hot reload
uvicorn src.api.main:app --reload --port 8080

# Run tests
pytest tests/
```

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

**Note**: The Quranic text and scholarly content are in the public domain. Please respect the licensing of individual data sources listed above.

---

## Acknowledgments

- The Quran open-source community for data contributions
- Classical scholars whose tafsirs are preserved digitally
- Open-source AI/ML community

---

<div align="center">

**Built with reverence for the Holy Quran**

للتواصل والاقتراحات | For feedback and suggestions

</div>
