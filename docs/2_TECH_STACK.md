# Technology Stack Specification
## AI-Powered Student Career & Opportunity Hub (`internpilot`)

**Document Version:** 2.0  
**Classification:** Technical Architecture & Dependencies  

---

## 1. Executive Stack Overview Matrix

The platform is designed with a strict **local-first, zero-cost, high-performance** engineering philosophy. Every component runs 100% locally on standard CPU hardware with zero external API fees or cloud vendor lock-in.

| Architectural Layer | Technology / Library | Version | Role & Functionality | Key Justification |
| :--- | :--- | :--- | :--- | :--- |
| **Frontend UI** | HTML5 / Vanilla CSS3 | Standard | Layout, glassmorphism design tokens, CSS grid/flexbox | Zero build step, instant load time, maximum design flexibility |
| **Frontend Logic** | Modern JavaScript (ES6+) | ES2022 | Client state, async API calls, dynamic persona switching, modals | No heavy node_modules bundle, high runtime speed, zero bundler friction |
| **Application Server** | **FastAPI** | `>=0.110.0` | Asynchronous REST API routing, dependency injection, Swagger docs | 300% faster than Flask/Django; native async; auto OpenAPI generation |
| **ASGI Web Server** | **Uvicorn** | `>=0.29.0` | High-throughput asynchronous HTTP server implementation | Production-grade async request handling with low memory footprint |
| **Data Validation** | **Pydantic v2** | `>=2.6.0` | Request/response schema enforcement & type serialization | Strict type safety, high parsing speed via Rust core |
| **Database Engine** | **SQLite 3** | `3.40+` | Relational, zero-configuration local ACID storage | Zero server configuration, self-contained single file, ultra-fast local reads |
| **ORM / Query Engine**| **SQLAlchemy** | `>=2.0.28` | Declarative database schema, indexing, transaction management | Enterprise-grade ORM, multi-criteria filtering, migration ready |
| **Embedding Engine** | **SentenceTransformers** | `>=2.6.1` | Local dense vector embeddings (`all-MiniLM-L6-v2`) | State-of-the-art semantic representations, 80MB size, runs on CPU |
| **Deep Learning Base**| **PyTorch** | `>=2.2.0` | Tensor computation engine for transformer models | Optimized local CPU inference without requiring dedicated GPUs |
| **Similarity / Math** | **Scikit-Learn** | `>=1.4.1` | Cosine similarity matrix calculation & vector normalization | Ultra-fast vectorized math operations and score normalization |
| **Primary PDF Parser** | **PyMuPDF (`fitz`)** | `>=1.24.0` | High-fidelity, C-accelerated PDF text extraction | 10x faster than pure-Python PDF parsers; accurate layout analysis |
| **Fallback PDF Parser**| **pypdf** | `>=4.1.0` | Pure-Python resilient PDF text extractor | Zero-dependency fallback if native C libraries fail to compile |
| **Telegram Scraping** | **Telethon / Bot API** | `>=1.34.0` | Automated ingestion from public student opportunity channels | Native MTProto support; handles rate limits & channel message streams |
| **Web Scraping** | **Playwright / BS4** | `>=1.42.0` | Headless browser & HTML parsing for dynamic web portals | Robust handling of client-side rendered job listing pages |
| **Security & Hashing**| **Passlib / Bcrypt** | `>=1.7.4` | Salted cryptographic password hashing for admin accounts | Industry-standard protection against dictionary and rainbow attacks |
| **Testing Framework** | **Pytest** | `>=8.1.1` | Comprehensive test runner for unit & integration testing | Parametrized fixtures, detailed assertions, 115+ automated tests |
| **Automation** | **Windows Batch (`run.bat`)** | CMD / CLI | Automated environment verification, venv setup, and server launch | Single double-click execution for users without technical expertise |

---

## 2. Frontend Layer Deep Dive

### 2.1 Modern Vanilla Architecture
Instead of using heavy JavaScript frameworks (React, Angular, Vue) or CSS compilers (Tailwind, Sass), `internpilot` utilizes native modern Web Standards:
- **Zero Build Tools**: No Webpack, Vite, or Babel required. Edit code and refresh immediately.
- **Glassmorphism Design System**: Custom CSS variables defined in `:root` provide consistent design tokens for dark and light modes, soft glowing borders, transparent cards, and smooth transitions.
- **Single-Page Application (SPA) State**: A single global state manager in `frontend/js/app.js` manages:
  - Active Student Persona (`Debasis Behera` vs `Priya Patel`)
  - Filter and search parameters (stipend, role, remote, match threshold)
  - Modal workflows (Resume review, Match inspection, Application confirmation)
  - Dynamic tab navigation across all 8 student tabs and the Admin suite.

### 2.2 UI Design Tokens (`frontend/css/style.css`)
```css
:root {
  --primary-accent: #6366f1;       /* Indigo 500 */
  --primary-accent-hover: #4f46e5; /* Indigo 600 */
  --surface-bg: #0f172a;           /* Slate 900 */
  --surface-card: rgba(30, 41, 59, 0.7); /* Translucent glass */
  --border-glass: rgba(255, 255, 255, 0.1);
  --success: #10b981;              /* Emerald 500 */
  --warning: #f59e0b;              /* Amber 500 */
  --danger: #ef4444;               /* Rose 500 */
  --text-primary: #f8fafc;
  --text-muted: #94a3b8;
  --font-family: 'Inter', system-ui, -apple-system, sans-serif;
}
```

---

## 3. Backend & Application Server

### 3.1 FastAPI & Uvicorn
- **Asynchronous Coroutines (`async` / `await`)**: High-concurrency processing allows non-blocking database queries, ingestion tasks, and real-time score streaming.
- **Automatic Swagger/OpenAPI Documentation**: Interactive documentation is auto-generated and served at `/docs` (Swagger UI) and `/redoc` (ReDoc), enabling seamless API inspection.
- **Dependency Injection**: Database sessions (`get_db`) and authentication tokens are cleanly injected into route handlers.

### 3.2 Pydantic v2 Serialization & Strict Typing
Every API request and response is strictly typed and validated at runtime:
```python
class OpportunityResponse(BaseModel):
    id: int
    title: str
    company: str
    location: str
    remote_status: str
    role_type: str
    stipend: Optional[str]
    skills: List[str]
    source: str
    verified: bool
    created_at: datetime

    class Config:
        from_attributes = True
```

---

## 4. Database & Persistence Layer

### 4.1 SQLite 3 with SQLAlchemy 2.0 ORM
- **Engine URL**: `sqlite:///./data/career_hub.db`
- **ACID Compliance**: Full Atomicity, Consistency, Isolation, and Durability guarantees.
- **Multi-Criteria Composite Indexes**:
  - `idx_opp_company_title`: Composite index on `company` + `title` for instant deduplication checks.
  - `idx_opp_status_verified`: B-tree index on `verified` and `is_active` for fast student feed queries.
  - `idx_opp_role_type`: Index on `role_type` and `remote_status` for sub-millisecond filtering.

### 4.2 Database Schema Architecture

```text
┌───────────────────────────┐         ┌───────────────────────────┐
│         STUDENTS          │         │       OPPORTUNITIES       │
├───────────────────────────┤         ├───────────────────────────┤
│ id (PK, Integer)          │         │ id (PK, Integer)          │
│ name (String)             │         │ title (String, Indexed)   │
│ email (String, Unique)    │         │ company (String, Indexed) │
│ degree (String)           │         │ location (String)         │
│ branch (String)           │         │ remote_status (String)    │
│ cgpa (Float)              │         │ role_type (String)        │
│ skills (JSON Array)       │         │ stipend (String)          │
│ preferred_roles (JSON)    │         │ required_skills (JSON)    │
│ preferred_locations (JSON)│         │ description (Text)        │
│ embedding (Vector Blob)   │         │ apply_url (String)        │
└─────────────┬─────────────┘         │ verified (Boolean)        │
              │                       │ embedding (Vector Blob)   │
              │                       └─────────────┬─────────────┘
              │                                     │
              ▼                                     ▼
┌───────────────────────────┐         ┌───────────────────────────┐
│       APPLICATIONS        │         │    SAVED_OPPORTUNITIES    │
├───────────────────────────┤         ├───────────────────────────┤
│ id (PK, Integer)          │         │ id (PK, Integer)          │
│ student_id (FK -> Students)         │ student_id (FK -> Students)
│ opp_id (FK -> Opps)       │         │ opp_id (FK -> Opps)       │
│ status (Applied/Interview)│         │ saved_at (DateTime)       │
│ interview_notes (Text)    │         └───────────────────────────┘
│ applied_at (DateTime)     │
└───────────────────────────┘
```

---

## 5. AI, NLP & Semantic Matching Engine

### 5.1 Hugging Face `SentenceTransformers` (`all-MiniLM-L6-v2`)
- **Architecture**: 6-layer MiniLM transformer fine-tuned for semantic sentence pairs.
- **Embedding Dimensionality**: 384 dimensions.
- **Model Footprint**: ~80MB file size, requiring ~200MB RAM during inference.
- **Inference Speed**: ~8ms per opportunity representation on standard Intel/AMD CPU.
- **Vector Representation**:
  - **Student Representation**: Synthesized text combining `[Name] + [Degree & Branch] + [Skills List] + [Preferred Roles] + [Projects & Summary]`.
  - **Job Representation**: Synthesized text combining `[Title] + [Company] + [Required Skills] + [Role Type] + [Cleaned Description]`.

### 5.2 Canonical Skill Taxonomy Engine
A curated dictionary of over 100 canonical technology and computer science skills with automated alias resolution:
- Example: `"py"` / `"python3"` / `"python-dev"` $\rightarrow$ `Python`
- Example: `"react.js"` / `"reactjs"` $\rightarrow$ `React`
- Example: `"k8s"` / `"kubernetes-cluster"` $\rightarrow$ `Kubernetes`
- Example: `"postgres"` / `"psql"` / `"postgresql"` $\rightarrow$ `PostgreSQL`

Regex boundary matching prevents false positives (e.g., matching the word `"go"` inside `"good"`, or `"c"` inside `"company"`).

### 5.3 6-Factor Hybrid Scoring Formula

$$\text{Total Fit Score} = W_1 S_{\text{semantic}} + W_2 S_{\text{skills}} + W_3 S_{\text{role}} + W_4 S_{\text{eligibility}} + W_5 S_{\text{location}} + W_6 S_{\text{experience}}$$

Where:
- $W_1 = 0.35$ (Cosine Similarity of 384-dim SentenceTransformer vectors)
- $W_2 = 0.30$ (Canonical technical skill overlap Jaccard ratio)
- $W_3 = 0.15$ (Student preferred role keyword match)
- $W_4 = 0.10$ (Degree, Branch, and CGPA requirement compliance)
- $W_5 = 0.05$ (Geographic target match or remote work compatibility)
- $W_6 = 0.05$ (Graduation year alignment with experience requirement)

---

## 6. Document & Resume Extraction Engine

### 6.1 Dual-Engine Strategy
1. **PyMuPDF (`fitz`)**: Fast C-based PDF parser extracting text blocks with coordinate fidelity and font size hints.
2. **`pypdf` Fallback**: Pure Python library ensuring that if a user runs the system in a restricted environment where C extensions cannot build, resume parsing continues seamlessly.

### 6.2 Regex Extraction Patterns
- **Email**: `[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+`
- **Phone**: `(?:\+?91[\-\s]?)?[6789]\d{9}` (Indian mobile format & international variants)
- **CGPA**: `(?:CGPA|GPA|Score)[\s:]*([0-9]+\.?[0-9]*)\s*(?:\/\s*10|\/\s*4)?`
- **Graduation Year**: `(?:20[2-3][0-9])`

---

## 7. Ingestion & Opportunity Scraping Pipeline

1. **Telethon / Telegram Bot API**: Connects to public engineering opportunity channels, listens for new message broadcasts, extracts entity URLs, and parses job criteria.
2. **CSV / JSON Ingestion Pipeline**: Ingests student placement cell files placed in `data/imports/`, normalizing columns (`Job Title`, `Company Name`, `Stipend`, `Location`).
3. **Multi-Signal Deduplication Pipeline**:
   - Primary: Exact URL SHA-256 hash.
   - Secondary: Normalized Levenshtein ratio on `company + title`. If similarity $> 0.88$, records are flagged as duplicates.

---

## 8. Development, Testing & Launcher Tooling

- **Test Suite**: Built on `pytest` (`tests/`), providing 115+ automated unit and integration tests covering API endpoints, scoring formulas, regex extraction, and deduplication logic.
- **One-Click Windows Launcher (`run.bat`)**:
  - Validates Python 3.10+ in PATH.
  - Automatically creates and activates `venv`.
  - Installs dependencies from `requirements.txt`.
  - Prepares default `.env` from `.env.example`.
  - Starts Uvicorn server and provides terminal link.

---

## 9. Justification: Why This Stack Was Chosen

| Technology Choice | Evaluated Alternative | Architectural Rationale for Selection |
| :--- | :--- | :--- |
| **FastAPI** | Django / Flask | Flask lacks native async and requires extra plugins for Swagger. Django is too heavy and tightly coupled to its own ORM. FastAPI gives async speed and auto-generated API docs. |
| **SentenceTransformers (`all-MiniLM-L6-v2`)** | OpenAI API / Cloud LLMs | Zero cost, 100% offline, absolute student privacy (resumes never leave the laptop), and deterministic, fast CPU inference. |
| **SQLite + SQLAlchemy** | PostgreSQL / MongoDB | Eliminates the need for students to install Docker or manage database server daemons. Zero setup required; instant portability. |
| **Vanilla JS & CSS** | React + Tailwind | Avoids `node_modules` (often 400MB+), complex build tools, and version conflicts. Native JavaScript loads instantly with zero compilation step. |
| **PyMuPDF + pypdf** | Cloud OCR / AWS Textract | Cloud OCR is slow, costs money per page, and leaks private student PII to the cloud. Local PDF parsing is instantaneous and completely private. |
