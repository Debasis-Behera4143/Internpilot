# 🎓 AI-Powered Student Career & Opportunity Hub

> **Final-Year Engineering Project**: An automated, intelligent, privacy-first career discovery and opportunity aggregation ecosystem designed specifically for college students and fresh graduates.

Transforming scattered, manual internship searches into an automated pipeline:
```text
SOURCE → COLLECT → NORMALIZE → EXTRACT STRUCTURED DATA → VALIDATE → DEDUPLICATE → EXPIRE OLD → STORE IN DB → AI MATCH → STUDENT DASHBOARD → APPLY NOW
```

---

## 🌟 Key Highlights

- **Real Data Integration & Validation (Step 5)**: 78+ realistic demonstration opportunities in `data/demo_opportunities_realistic.csv` across AI/ML, Data Science, Web Development, Cloud/DevOps, Cybersecurity, QA, and Research with diverse locations, deadlines, and source attributions.
- **System Health Diagnostics & Demo Reset CLI**:
  - `python main.py --health`: Full terminal diagnostic check covering Database, API routes, Hybrid Scorer, SentenceTransformer embedding engine, Opportunity DB, and Demo Personas.
  - `python main.py --seed-demo`: One-command pristine reset initializing SQLite tables, ingesting realistic opportunities, and resetting demo bookmarks/applications to baseline.
- **Complete Student Career Hub (Step 4)**: 8-tab student navigation shell featuring Dashboard, Opportunities Explorer, Recommended For You, Saved Opportunities, Application Tracker, Skill Gap Dashboard, Profile & Resume, and Settings & Alerts.
- **Multi-Source Ingestion Pipeline (Step 2)**: Ingests student internships and fresher roles from public Telegram career channels, compliant LinkedIn exports, bulk CSV/JSON files, and direct employer/college submissions with multi-signal deduplication, normalizer, and cutoff expiry.
- **AI Career Matching Engine (Step 3)**: Multi-factor hybrid recommender combining semantic similarity (35%), technical skill compatibility (30%), role preference alignment (15%), academic eligibility (10%), location/remote compatibility (5%), and experience alignment (5%).
- **Evaluator Demo Personas**: One-click top-bar switcher between **Student A (Debasis Behera - AIML)** and **Student B (Priya Patel - Web/Backend)** demonstrating instant personalization across recommendations and skill gap roadmaps.
- **Apply-Now Integrity & Tracking Flow**: Direct official URL opening (`window.open`) with a post-apply confirmation prompt that seamlessly logs submissions into the Application Tracker (strictly safe: no automated bot submission or ATS interference).
- **Persistent Saved Bookmarks**: Database-backed saved opportunities table in SQLite with duplicate bookmark prevention.
- **Aggregated Skill Gap Dashboard**: Identifies high-frequency missing technical skills across recommended roles and classifies them into High, Medium, and Optional learning tiers.
- **Local PDF Resume Parser**: Parses PDF resumes locally using PyMuPDF (`fitz`) and `pypdf` without paid APIs; displays an interactive preview and requires explicit user confirmation before applying to the profile.
- **100% Free & Privacy-Preserving**: No OpenAI, Gemini, Claude, or paid embedding APIs. All data and AI vector embeddings remain on-device.
- **Rigorous Automated Testing**: 115 comprehensive unit and integration tests passing with 100% success (0 failed).

---

## 🏗️ System Architecture

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        STUDENT WEB DASHBOARD                           │
│  (Opportunities Feed, Opportunity Explorer, Ingest Trigger, Submissions)│
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ HTTP / REST APIs
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                          FASTAPI BACKEND                               │
│  /api/opportunities  │  /api/matching  │  /api/applications  │ /student│
└──────┬────────────────────────────┬────────────────────────────┬───────┘
       │                            │                            │
       ▼                            ▼                            ▼
┌──────────────────────────┐ ┌───────────────┐           ┌───────────────┐
│ REAL INGESTION ENGINE    │ │ LOCAL AI / ML │           │  DATA & ORM   │
│ Multi-Source Pipeline:   │ │ Sentence-     │           │ SQLite DB     │
│ • YC Startup Scraper     │ │ Transformers  │           │ (career_hub)  │
│ • Wellfound Scraper      │ │ Cosine Sim    │           │ DB Indexing   │
│ • Internshala Scraper    │ │ Skill Gap Rad │           │ JSON Fallback │
│ • Telegram Public Chan   │ └───────┬───────┘           │ Sync Layer    │
│ • Compliant LinkedIn Exp │         │                   └───────────────┘
│ • Generic CSV/JSON Imprt │         │
│ • Employer/College Submit│         │
│ ── Normalization ──      │         │
│ ── Deduplication ──      │         │
│ ── Expiry Lifecycle ──── │         │
└──────────────────────────┘         │
                                     ▼
                          ┌──────────┴──────────┐
                          ▼                     ▼
                   ┌──────────────┐     ┌───────────────┐
                   │ Google / IN  │     │ Telegram Bot  │
                   │ Recruiter Qs │     │ Match Alerts  │
                   └──────────────┘     └───────────────┘
```

---

## 📂 Project Structure

```text
internpilot/
├── backend/
│   ├── api/
│   │   ├── app.py                      # FastAPI application with lifespan management
│   │   ├── routes_opportunities.py     # Filtered feeds, stats, ingestion, submission
│   │   ├── routes_matching.py          # AI matching & skill gap endpoints
│   │   ├── routes_student.py           # Student profile read/update
│   │   └── routes_applications.py      # Application tracker endpoints
│   ├── collectors/
│   │   ├── normalizer.py               # Text, company, location, skill, & URL cleaning
│   │   ├── telegram_collector.py       # Compliant public channel web preview collector
│   │   ├── linkedin_collector.py       # Safe adapter for exported files & official API
│   │   ├── import_collector.py         # CSV & JSON bulk file importer
│   │   └── __init__.py                 # Exported collector interfaces
│   ├── database/
│   │   └── db.py                       # SQLAlchemy models, SQLite engine, indexed schema
│   ├── models/
│   │   ├── opportunity.py              # Pydantic & domain Opportunity schema
│   │   ├── student.py                  # Student profile schema
│   │   └── application.py              # Application status schema
│   └── services/
│       ├── ingestion_service.py        # Orchestration pipeline with failure isolation
│       ├── deduplication_service.py    # Multi-signal hierarchical deduplication
│       ├── expiry_service.py           # Cutoff date & staleness lifecycle manager
│       ├── opportunity_service.py      # SQLite repository & advanced query filters
│       ├── matching_service.py         # SentenceTransformers semantic matcher
│       └── student_service.py          # Profile management service
├── scrapers/
│   ├── yc.py                           # Y Combinator Work at a Startup scraper
│   ├── wellfound.py                    # Wellfound open listings scraper
│   └── internshala.py                  # Internshala internship collector
├── data/
│   ├── career_hub.db                   # SQLite production database with indexes
│   ├── jobs.json                       # Synced JSON opportunity cache
│   ├── profile.json                    # Default student profile
│   ├── applications.json               # Synced student applications
│   └── imports/                        # Directory for CSV/JSON bulk imports
│       ├── sample_opportunities.csv    # Sample CSV for quick testing
│       └── sample_opportunities.json   # Sample JSON for quick testing
├── docs/
│   ├── 1_SRS.md                        # Complete Software Requirements Specification
│   ├── 2_TECH_STACK.md                 # Full technology stack & architectural rationale
│   ├── 3_ARCHITECTURE_AND_FLOW.md      # System architecture & step-by-step Mermaid flowcharts
│   └── 4_PROJECT_REPORT.md             # Master project report, API catalog & evaluation guide
├── frontend/
│   ├── index.html                      # Modern responsive web dashboard
│   ├── css/style.css                   # Custom responsive CSS
│   └── js/app.js                       # Frontend state, API integration, modals
├── tests/
│   ├── test_normalizer.py              # Unit tests for text & skill normalization
│   ├── test_deduplication.py           # Unit tests for multi-signal deduplication
│   ├── test_expiry.py                  # Unit tests for deadline & age expiration
│   ├── test_import_collector.py        # Unit tests for CSV/JSON parsing
│   ├── test_collectors_isolation.py    # Tests for collector fault isolation
│   ├── test_api_ingestion.py           # Integration tests for FastAPI endpoints
│   ├── test_matching.py                # Tests for local AI cosine similarity
│   ├── test_skill_gap.py               # Tests for skill gap analysis
│   └── test_tracker.py                 # Tests for application tracking
├── main.py                             # Unified CLI & server entrypoint
├── requirements.txt                    # Project dependencies
└── README.md
```

---

## ⚙️ Installation & Setup

### 1. Prerequisites
- **Python 3.10+** (Python 3.11, 3.12, 3.13, 3.14 supported)
- Git

### 2. Clone the Repository
```bash
git clone https://github.com/YOUR_USERNAME/internpilot.git
cd internpilot
```

### 3. Set Up Virtual Environment
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux / macOS
python3 -m venv venv
source venv/bin/activate
```

### 4. Install Dependencies
```bash
pip install -r requirements.txt
```

*(Optional: If you want to enable live headless browser scraping for dynamic JavaScript sites, run `playwright install chromium`)*

---

## 🚀 Running the Platform

> 📖 **Looking for a detailed setup guide?** See the comprehensive [**Complete Run & Setup Guide (HOW_TO_RUN.md)**](HOW_TO_RUN.md).

### Start the Web Application & API Server
```bash
python main.py --api
```
- **Web Dashboard**: Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your browser.
- **Interactive API Docs (Swagger)**: Open [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

### Trigger Ingestion Engine from CLI
```bash
python main.py --ingest
```
Runs the full ingestion pipeline: collects across all configured sources, normalizes records, strips tracking parameters, eliminates duplicates, marks expired listings, and stores fresh opportunities in `data/career_hub.db`.

### Other CLI Options
```bash
# Test local AI semantic matching on current database
python main.py --test-matching

# Run the legacy console interactive assistant
python main.py --interactive

# Display CLI help
python main.py --help
```

---

## 📥 Bulk Opportunity Imports

You can easily ingest external internship listings in bulk by placing files in `data/imports/` and running `--ingest` (or calling `POST /api/opportunities/ingest`).

### CSV Format Example (`data/imports/sample_opportunities.csv`)
```csv
title,company,description,opportunity_type,skills,location,remote,stipend,deadline,apply_url
"AI Research Intern","DeepMind Research","Work on transformer architectures","internship","Python, PyTorch, Machine Learning","Bengaluru",true,"₹60,000 / month",2026-10-31,"https://careers.google.com/jobs/ai-research-intern"
"Frontend Engineer","Zomato Tech","React & Next.js dashboard development","full-time","React, JavaScript, TypeScript","Gurugram",false,"₹12 LPA",2026-08-15,"https://zomato.com/careers/frontend"
```

### JSON Format Example (`data/imports/sample_opportunities.json`)
```json
[
  {
    "title": "Machine Learning Intern",
    "company": "Swiggy Labs",
    "description": "Develop ranking models for delivery recommendation.",
    "opportunity_type": "internship",
    "skills": ["Python", "Machine Learning", "Scikit-Learn"],
    "location": "Bengaluru, India",
    "remote": true,
    "stipend": "₹45,000 / month",
    "deadline": "2026-09-30",
    "apply_url": "https://careers.swiggy.com/ml-intern"
  }
]
```

---

## 🏢 Employer & College Direct Submissions

Employers or College Placement Cells can programmatically submit verified opportunities via REST API:

```bash
curl -X POST "http://127.0.0.1:8000/api/opportunities/submit" \
     -H "Content-Type: application/json" \
     -d '{
       "title": "Data Science Intern",
       "company": "Campus Placement Drive",
       "description": "On-campus internship drive for 2026 batch.",
       "opportunity_type": "internship",
       "skills": ["Python", "SQL", "Pandas"],
       "location": "Hyderabad, India",
       "remote": false,
       "stipend": "₹35,000 / month",
       "deadline": "2026-10-15",
       "apply_url": "https://college-portal.edu/placements/ds-drive",
       "source": "College Placement Cell"
     }'
```

---

## 🧪 Testing & Validation

The project includes an automated test suite covering all ingestion, normalization, deduplication, expiry, and API operations:

```bash
python -m pytest tests/ -v
```

All 65 unit and integration tests validate:
- **`test_skill_dictionary.py`**: 100+ skill canonicalization, alias resolution, and word-boundary safety.
- **`test_resume_parser.py`**: Heuristic PDF resume parsing (PyMuPDF / pypdf), contact, education, skills, and projects recovery.
- **`test_representations.py`**: Student and job text synthesizers for dense embeddings.
- **`test_embedder_cache.py`**: SentenceTransformers embedding generation, LRU cache retrieval, and offline fallback.
- **`test_hybrid_scoring.py`**: Subscore decomposition, weight calculations, relative ranking, and empty edge cases.
- **`test_explanation.py`**: Natural language explanation generation and prioritized skill gap classification.
- **`test_personalization_diff.py`**: Distinct recommendation outputs for Student A (AI/ML) vs Student B (Web/Backend).
- **`test_api_matching.py`**: `/api/matching/recommendations`, `/api/matching/run`, and `/api/students/resume` multipart upload.
- **`test_normalizer.py`**: Company suffix stripping, location canonicalization, 40+ skill aliases, URL de-tracking.
- **`test_deduplication.py`**: Exact URL matching, fuzzy title ratio, and distinct role keyword protection.
- **`test_expiry.py`**: Cutoff date validation, 60-day staleness, status transitions.
- **`test_import_collector.py`**: CSV/JSON parsing, missing field handling, column alias resilience.
- **`test_collectors_isolation.py`**: Failure isolation across collectors during pipeline execution.
- **`test_api_ingestion.py`**: Opportunity feed filtering, submissions, and pagination.
- **`test_matching.py` & `test_skill_gap.py`**: Cosine similarity and baseline skill gaps.
- **`test_models.py` & `test_tracker.py`**: Domain entities and application tracking.

---

## 🛡️ Ethical Scraping & Privacy Standards

1. **No Unauthorized Scraping**: We strictly do not bypass authentication, solve CAPTCHAs, or violate anti-scraping protections on private portals.
2. **Transparent Sourcing**: Every single listing preserves its original attribution (`source`), `source_url`, and original `apply_url`.
3. **Direct Applications**: The student dashboard directs applicants straight to official company links; no user credentials or resumes are intercepted.
4. **Local Data & AI**: All profile data, PDF resumes, application records, and AI vector embeddings remain 100% on the student's machine.

---

## 📜 Author & License

- **Developer & Lead**: **Debasis Behera**
- **Project**: **AI-Powered Student Career & Opportunity Hub** (Final-Year Engineering Project)
- **License**: [MIT License](LICENSE)

